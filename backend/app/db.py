"""플레이 기록 저장소 (SQLite). — 담당: 장우석

왜 필요한가
- 지금까지 세션은 서버 메모리에만 있어서, 서버를 껐다 켜면 플레이 기록·리포트·통계가 사라졌다.
- 매 턴이 끝날 때 여기 저장하면 ① 새로고침·서버 재시작 후 이어하기 ② 운영자 통계 ③ 1회 플레이 비용 실측이 된다.

테이블 (docs/architecture.md 의 DB 초안 그대로)
  sessions   : 세션 1개 = 1판. 현재 단계·위험도·기회 등 상태값 + 시작 당시 시나리오 사본
  messages   : 대화 기록 (화면에 보인 순서대로)
  decisions  : 판단 타임라인 (리포트의 '내 선택이 만든 경로')
  reports    : 완성된 리포트 (다시 열어도 AI를 또 부르지 않음)
  llm_calls  : AI 호출 1번마다 토큰·응답 시간·성공 여부 → 비용 계산의 근거

규칙
- 표준 SQL만 쓴다 (배포 때 PostgreSQL 로 옮기기 쉽게).
- 요청마다 연결을 새로 열고 닫는다 (FastAPI 가 여러 스레드에서 동시에 부르기 때문). 쓰기는 잠금으로 한 번에 하나씩.
- 경로는 환경변수 MIA_DB_PATH (기본: backend/mia.db, 깃에 올라가지 않음).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "mia.db"
SESSION_TTL_HOURS = 24            # 마지막 활동 후 이 시간이 지난 '진행 중' 세션은 이어할 수 없다 (만료)
_write_lock = threading.Lock()
_ready: set[str] = set()          # 이미 테이블을 만든 DB 파일 경로

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    scenario_id      TEXT NOT NULL,
    scenario_version TEXT,
    status           TEXT NOT NULL,             -- playing | cleared | failed
    stage_index      INTEGER NOT NULL,
    risk             INTEGER NOT NULL,
    turns_in_stage   INTEGER NOT NULL,
    free_turns       INTEGER NOT NULL DEFAULT 0,
    blocked_count    INTEGER NOT NULL DEFAULT 0,
    state_json       TEXT NOT NULL,             -- stage_results, actions, evidence, conditions
    scenario_json    TEXT NOT NULL,             -- 시작 당시 시나리오 사본 (나중에 시나리오가 바뀌어도 이 판은 그대로)
    started_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    ended_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_scenario ON sessions(scenario_id);

CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    seq        INTEGER NOT NULL,
    stage      INTEGER NOT NULL,
    role       TEXT NOT NULL,                   -- user | character | narrator | system
    name       TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);

CREATE TABLE IF NOT EXISTS decisions (
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    seq         INTEGER NOT NULL,
    stage       INTEGER NOT NULL,
    title       TEXT NOT NULL,
    action      TEXT NOT NULL,
    verdict     TEXT NOT NULL,
    risk_before INTEGER NOT NULL,
    risk_after  INTEGER NOT NULL,
    outcome     TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);

CREATE TABLE IF NOT EXISTS reports (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    passed     INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    body_json  TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    scenario_id   TEXT NOT NULL,
    purpose       TEXT NOT NULL,                -- judge | evaluate
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens  INTEGER NOT NULL DEFAULT 0,
    latency_ms    INTEGER,
    result        TEXT NOT NULL,                -- ok | fallback
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_scenario ON llm_calls(scenario_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path() -> str:
    return os.getenv("MIA_DB_PATH", "").strip() or str(DEFAULT_PATH)


@contextmanager
def connect():
    path = db_path()
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        if path not in _ready:
            conn.execute("PRAGMA journal_mode=WAL")   # 읽기와 쓰기가 서로 막지 않게
            conn.executescript(SCHEMA)
            _ready.add(path)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- 세션 저장·불러오기 ----------

def save_session(s, saved_messages: int, saved_decisions: int) -> tuple[int, int]:
    """세션 상태를 저장하고, 지난번 저장 이후 새로 생긴 대화·판단만 추가한다.
    반환: 이번까지 저장된 (대화 수, 판단 수) — 다음 저장 때 이어서 쓰기 위함.
    """
    ts = now()
    state = {"stage_results": s.stage_results, "actions": s.actions,
             "evidence": s.evidence, "conditions": s.conditions}
    with _write_lock, connect() as conn:
        conn.execute(
            """INSERT INTO sessions (id, scenario_id, scenario_version, status, stage_index, risk, turns_in_stage,
                                     free_turns, blocked_count, state_json, scenario_json, started_at, updated_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status, stage_index=excluded.stage_index,
                 risk=excluded.risk, turns_in_stage=excluded.turns_in_stage, free_turns=excluded.free_turns,
                 blocked_count=excluded.blocked_count, state_json=excluded.state_json,
                 updated_at=excluded.updated_at, ended_at=COALESCE(sessions.ended_at, excluded.ended_at)""",
            (s.id, s.scenario["id"], s.scenario.get("version"), s.status, s.stage_index, s.risk, s.turns_in_stage,
             s.free_turns_in_stage, s.blocked_count, json.dumps(state, ensure_ascii=False),
             json.dumps(s.scenario, ensure_ascii=False), ts, ts, ts if s.status != "playing" else None))
        new_msgs = s.transcript[saved_messages:]
        conn.executemany(
            "INSERT INTO messages (session_id, seq, stage, role, name, text, created_at) VALUES (?,?,?,?,?,?,?)",
            [(s.id, saved_messages + i, m["stage"], m["role"], m["name"], m["text"], ts) for i, m in enumerate(new_msgs)])
        new_dec = s.timeline[saved_decisions:]
        conn.executemany(
            """INSERT INTO decisions (session_id, seq, stage, title, action, verdict, risk_before, risk_after, outcome)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [(s.id, saved_decisions + i, d["stage"], d["title"], d["action"], d["verdict"],
              d["risk_before"], d["risk_after"], d["outcome"]) for i, d in enumerate(new_dec)])
    return len(s.transcript), len(s.timeline)


def load_session(session_id: str) -> dict | None:
    """저장된 세션을 dict 로 돌려준다. 없거나 만료됐으면 None. (Session 객체로 바꾸는 건 harness 가 한다)"""
    with connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        if row["status"] == "playing" and _expired(row["updated_at"]):
            return None
        messages = [dict(r) for r in conn.execute(
            "SELECT stage, role, name, text FROM messages WHERE session_id = ? ORDER BY seq", (session_id,))]
        decisions = [dict(r) for r in conn.execute(
            """SELECT stage, title, action, verdict, risk_before, risk_after, outcome
               FROM decisions WHERE session_id = ? ORDER BY seq""", (session_id,))]
        report = conn.execute("SELECT body_json FROM reports WHERE session_id = ?", (session_id,)).fetchone()
    data = dict(row)
    data["state"] = json.loads(data.pop("state_json"))
    data["scenario"] = json.loads(data.pop("scenario_json"))
    data["messages"] = messages
    data["decisions"] = decisions
    data["report"] = json.loads(report["body_json"]) if report else None
    return data


def _expired(updated_at: str) -> bool:
    try:
        return datetime.fromisoformat(updated_at) < datetime.now(timezone.utc) - timedelta(hours=SESSION_TTL_HOURS)
    except ValueError:
        return True


def save_report(session_id: str, report: dict) -> None:
    with _write_lock, connect() as conn:
        conn.execute("INSERT OR IGNORE INTO reports (session_id, passed, total, body_json, created_at) VALUES (?,?,?,?,?)",
                     (session_id, report["passed"], report["total"], json.dumps(report, ensure_ascii=False), now()))


def log_llm_call(session_id: str, scenario_id: str, purpose: str, model: str, usage: dict | None,
                 latency_ms: int | None, result: str) -> None:
    usage = usage or {}
    with _write_lock, connect() as conn:
        conn.execute(
            """INSERT INTO llm_calls (session_id, scenario_id, purpose, model, input_tokens, output_tokens,
                                      total_tokens, latency_ms, result, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (session_id, scenario_id, purpose, model or "unknown", int(usage.get("promptTokenCount", 0) or 0),
             int(usage.get("candidatesTokenCount", 0) or 0), int(usage.get("totalTokenCount", 0) or 0),
             latency_ms, result, now()))


# ---------- 통계 (운영자 CMS) ----------

def scenario_stats(scenario_id: str) -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT status, state_json FROM sessions WHERE scenario_id = ?", (scenario_id,)).fetchall()
        llm = conn.execute(
            """SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens,
                      COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(AVG(latency_ms),0) AS avg_latency,
                      COALESCE(SUM(result = 'fallback'),0) AS fallbacks
               FROM llm_calls WHERE scenario_id = ? AND model != 'mock'""", (scenario_id,)).fetchone()
    finished = [r for r in rows if r["status"] != "playing"]
    stage_fail: dict[int, int] = {}
    passed_total = 0
    for r in finished:
        results = json.loads(r["state_json"]).get("stage_results", {})
        passed_total += sum(v == "correct" for v in results.values())
        for no, v in results.items():
            if v != "correct":
                stage_fail[int(no)] = stage_fail.get(int(no), 0) + 1
    tokens = {"calls": llm["calls"], "input_tokens": llm["input_tokens"], "output_tokens": llm["output_tokens"],
              "avg_latency_ms": round(llm["avg_latency"]), "fallbacks": llm["fallbacks"]}
    tokens["cost_per_play_krw"] = _cost_per_play(tokens, len(rows))
    return {
        "plays": len(rows),
        "finished": len(finished),
        "cleared": sum(r["status"] == "cleared" for r in finished),
        "avg_passed": round(passed_total / len(finished), 1) if finished else None,
        "stage_fail": stage_fail,
        "ai": tokens,
    }


def _cost_per_play(tokens: dict, plays: int) -> float | None:
    """.env 의 PRICE_* (100만 토큰당 달러)가 설정돼 있을 때만 1판당 평균 비용(원)을 계산한다."""
    p_in = float(os.getenv("PRICE_FAST_INPUT_PER_M", "0") or 0)
    p_out = float(os.getenv("PRICE_FAST_OUTPUT_PER_M", "0") or 0)
    if not plays or not tokens["calls"] or not (p_in or p_out):
        return None
    usd = tokens["input_tokens"] * p_in / 1e6 + tokens["output_tokens"] * p_out / 1e6
    return round(usd * float(os.getenv("USD_TO_KRW", "1400") or 1400) / plays, 2)
