"""운영자 CMS API — 시나리오 만들기·고치기·공개하기, 이용 현황.

- 모든 요청은 헤더 `X-Admin-Token` 이 .env 의 ADMIN_TOKEN 과 같아야 한다. ADMIN_TOKEN 이 비어 있으면 CMS는 꺼진다.
- 시나리오는 지금처럼 data/scenarios/<id>.json 파일로 저장한다. (DB는 4주차. 저장 방식만 바꾸면 되도록 이 파일에 모아 둠)
- 저장 전 scenario_check 로 검사한다. 오류가 있으면 저장하지 않고, 공개는 오류 0개일 때만 된다.
- 이용자에게는 status=published 인 시나리오만 보인다. (main.py)
"""
from __future__ import annotations

import copy
import hmac
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from . import harness, scenario_check

router = APIRouter(prefix="/admin", tags=["운영자 CMS"])


def admin_token_ok(token: str | None) -> bool:
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    return bool(expected) and bool(token) and hmac.compare_digest(token, expected)


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not os.getenv("ADMIN_TOKEN", "").strip():
        raise HTTPException(503, "운영자 기능이 꺼져 있습니다. .env 에 ADMIN_TOKEN 을 설정하세요.")
    if not admin_token_ok(x_admin_token):
        raise HTTPException(401, "운영자 토큰이 올바르지 않습니다.")


class NewScenario(BaseModel):
    id: str = Field(..., max_length=40)
    title: str = Field(..., min_length=1, max_length=80)
    category: str = Field("화재", max_length=20)


class StatusChange(BaseModel):
    status: str


def _path(scenario_id: str):
    if not scenario_check.ID_RE.match(scenario_id):
        raise HTTPException(400, "시나리오 id 형식이 올바르지 않습니다.")
    return harness.SCENARIO_DIR / f"{scenario_id}.json"


def _get(scenario_id: str) -> dict:
    sc = harness.SCENARIOS.get(scenario_id)
    if not sc:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    return sc


def _write(sc: dict) -> None:
    """임시 파일에 쓴 뒤 바꿔치기 → 저장 도중 서버가 꺼져도 파일이 반쯤 깨지지 않는다."""
    path = _path(sc["id"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    harness.SCENARIOS[sc["id"]] = sc


def _stats(scenario_id: str) -> dict:
    """서버 메모리의 플레이 기록으로 집계 (서버 재시작 시 초기화 — DB 저장 후 정확해짐)."""
    sessions = [s for s in harness.SESSIONS.values() if s.scenario.get("id") == scenario_id]
    finished = [s for s in sessions if s.status != "playing"]
    stage_fail: dict[int, int] = {}
    for s in finished:
        for no, result in s.stage_results.items():
            if result != "correct":
                stage_fail[no] = stage_fail.get(no, 0) + 1
    return {
        "plays": len(sessions),
        "finished": len(finished),
        "cleared": sum(s.status == "cleared" for s in finished),
        "avg_passed": round(sum(sum(r == "correct" for r in s.stage_results.values()) for s in finished) / len(finished), 1) if finished else None,
        "stage_fail": stage_fail,
    }


def _summary(sc: dict) -> dict:
    result = scenario_check.check(sc)
    return {
        "id": sc["id"], "title": sc.get("title", ""), "category": sc.get("category", ""),
        "status": sc.get("status", "published"), "version": sc.get("version", ""),
        "updated_at": sc.get("updated_at"), "total_stages": len(sc.get("stages") or []),
        "errors": len(result["errors"]), "warnings": len(result["warnings"]),
        "stats": _stats(sc["id"]),
    }


def _template(new: NewScenario) -> dict:
    """새 시나리오의 뼈대. 바로 저장·미리 플레이가 되도록 1단계짜리 예시를 채워 둔다."""
    return {
        "id": new.id, "version": "0.1", "status": "draft",
        "title": new.title, "summary": "한 줄 소개를 써 주세요.", "category": new.category,
        "thumbnail": "", "estimated_minutes": 5, "max_risk": 6,
        "briefing": {"role": "이용자의 역할", "mission": "이용자가 이뤄야 할 목표", "focus": ["연습할 역량"]},
        "role_doc": {
            "place": "장소", "situation": "전체 상황",
            "rules": ["캐릭터는 실제 현장의 사람처럼 짧고 급박하게 말한다 (1~2문장).",
                      "캐릭터는 정답이나 올바른 행동을 먼저 알려주지 않는다. 이용자가 판단하게 둔다.",
                      "선정적·폭력적 묘사, 욕설은 하지 않는다."],
            "world_facts": [],
        },
        "characters": [{"id": "partner", "name": "동료", "role": "함께 있는 사람",
                        "personality": "성격", "speech_style": "말투", "image": ""}],
        "stages": [{
            "stage": 1, "title": "첫 장면", "situation": "이 단계의 상황", "character_id": "partner",
            "opening_line": "캐릭터의 첫 대사", "correct_action": "공공기관 행동요령에 근거한 올바른 행동",
            "keywords": ["행동 키워드"], "wrong_keywords": [], "next_if_correct": None,
            "if_wrong": {"narration": "틀렸을 때 상황 변화", "risk_delta": 2},
            "reactions": {"correct": "맞았을 때 대사", "wrong": "틀렸을 때 대사", "unclear": "애매할 때 대사"},
            "partial_reply": "일부만 했을 때 대사", "facts": [], "image": "",
            "rubric": [], "danger_patterns": [],
        }],
        "evaluation": [{"id": "c1", "stage": 1, "criterion": "리포트에 표시할 평가 기준"}],
        "sources": [],
    }


@router.get("/scenarios", dependencies=[Depends(require_admin)])
def list_scenarios():
    return [_summary(sc) for sc in harness.SCENARIOS.values()]


@router.get("/scenarios/{scenario_id}", dependencies=[Depends(require_admin)])
def get_scenario(scenario_id: str):
    sc = _get(scenario_id)
    return {"scenario": sc, **scenario_check.check(sc), "stats": _stats(scenario_id)}


@router.post("/scenarios", dependencies=[Depends(require_admin)], status_code=201)
def create_scenario(new: NewScenario):
    if not scenario_check.ID_RE.match(new.id):
        raise HTTPException(422, "id: 영문 소문자로 시작하고 소문자·숫자·밑줄만 3~40자 (예: earthquake_school)")
    if new.id in harness.SCENARIOS or _path(new.id).exists():
        raise HTTPException(409, "같은 id 의 시나리오가 이미 있습니다.")
    sc = _template(new)
    sc["updated_at"] = _now()
    _write(sc)
    return {"scenario": sc, **scenario_check.check(sc)}


@router.post("/scenarios/{scenario_id}/duplicate", dependencies=[Depends(require_admin)], status_code=201)
def duplicate_scenario(scenario_id: str, new: NewScenario):
    """기존 시나리오를 복사해 새로 시작 (예: 오피스 화재 → 학교 화재)."""
    if not scenario_check.ID_RE.match(new.id):
        raise HTTPException(422, "id 형식이 올바르지 않습니다.")
    if new.id in harness.SCENARIOS or _path(new.id).exists():
        raise HTTPException(409, "같은 id 의 시나리오가 이미 있습니다.")
    sc = copy.deepcopy(_get(scenario_id))
    sc.update({"id": new.id, "title": new.title, "category": new.category, "status": "draft",
               "version": "0.1", "updated_at": _now()})
    _write(sc)
    return {"scenario": sc, **scenario_check.check(sc)}


@router.put("/scenarios/{scenario_id}", dependencies=[Depends(require_admin)])
def save_scenario(scenario_id: str, sc: dict):
    _get(scenario_id)
    if sc.get("id") != scenario_id:
        raise HTTPException(400, "시나리오 id 는 바꿀 수 없습니다. 복제해서 새로 만드세요.")
    if len(json.dumps(sc, ensure_ascii=False)) > 300_000:
        raise HTTPException(413, "시나리오가 너무 큽니다.")
    result = scenario_check.check(sc)
    if result["errors"]:
        raise HTTPException(422, {"message": "저장할 수 없습니다. 오류를 고쳐 주세요.", **result})
    sc["updated_at"] = _now()
    _write(sc)
    return {"scenario": sc, **result}


@router.post("/scenarios/{scenario_id}/status", dependencies=[Depends(require_admin)])
def change_status(scenario_id: str, change: StatusChange):
    if change.status not in scenario_check.STATUSES:
        raise HTTPException(422, "status 는 draft 또는 published")
    sc = copy.deepcopy(_get(scenario_id))
    result = scenario_check.check(sc)
    if change.status == "published" and result["errors"]:
        raise HTTPException(422, {"message": "오류가 있어 공개할 수 없습니다.", **result})
    sc["status"] = change.status
    sc["updated_at"] = _now()
    _write(sc)
    return _summary(sc)


@router.post("/validate", dependencies=[Depends(require_admin)])
def validate(sc: dict):
    """저장하지 않고 검사만 (편집 중 미리 확인용)."""
    return scenario_check.check(sc)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
