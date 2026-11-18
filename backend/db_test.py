"""DB 저장 검증 — 서버 재시작을 흉내 내서 이어하기·리포트·통계·AI 호출 기록이 남는지 본다.

실행: python -X utf8 db_test.py   (임시 DB 파일 사용, 실제 AI 호출 없음)
"""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["MIA_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "db_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import db, harness  # noqa: E402
from app.main import app  # noqa: E402


def restart_server():
    """서버를 껐다 켠 것처럼 메모리의 세션을 모두 비운다 (DB만 남음)."""
    harness.SESSIONS.clear()


class DbTests(unittest.TestCase):
    def setUp(self):
        for p in [patch("app.ai._api_key", return_value=None), patch.dict(os.environ, {"ADMIN_TOKEN": "t"})]:
            p.start()
            self.addCleanup(p.stop)
        self.c = TestClient(app)

    def start(self):
        r = self.c.post("/sessions", json={"scenario_id": "fire_office"})
        self.assertEqual(r.status_code, 200)
        return r.json()["session_id"]

    def say(self, sid, text):
        return self.c.post(f"/sessions/{sid}/messages", json={"text": text}).json()

    def test_resume_after_restart_keeps_state_and_conversation(self):
        sid = self.start()
        self.say(sid, "불이야!")                       # 일부 행동만 (근거 1개)
        before = self.say(sid, "소화기 어디 있어?")      # 질문 (기회 미사용)
        restart_server()
        r = self.c.get(f"/sessions/{sid}")
        self.assertEqual(r.status_code, 200)
        turn = r.json()
        self.assertEqual(turn["stage"], before["stage"])
        self.assertEqual(turn["attempts_left"], before["attempts_left"])
        self.assertIn("불이야!", [m["text"] for m in turn["messages"]])
        # 이어서 플레이하면 앞에서 모은 근거(불이야)와 합쳐져 통과해야 한다
        after = self.say(sid, "119에 신고할게요")
        self.assertEqual(after["stage"], 2)

    def test_full_play_report_survives_restart_without_recomputing(self):
        sid = self.start()
        for text in ["불이야! 119에 신고할게요", "엘리베이터 타지 마! 계단으로 가자",
                     "소매로 코와 입을 막고 자세를 낮춰서 가자", "열기 전에 손등으로 손잡이 뜨거운지 확인하자",
                     "7층 탕비실에서 불이 났어요. 지훈아 노트북 가지러 들어가지 마!"]:
            self.say(sid, text)
        first = self.c.get(f"/sessions/{sid}/report").json()
        self.assertEqual(first["passed"], 5)
        restart_server()
        with patch("app.ai.evaluate") as evaluate:
            again = self.c.get(f"/sessions/{sid}/report")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json(), first)
        evaluate.assert_not_called()                     # 저장된 리포트를 그대로 사용
        self.assertEqual(self.c.post(f"/sessions/{sid}/messages", json={"text": "또"}).status_code, 400)

    def test_messages_are_not_duplicated_across_saves(self):
        sid = self.start()
        for _ in range(3):
            self.say(sid, "소화기 어디 있어?")
        restart_server()
        texts = [m["text"] for m in self.c.get(f"/sessions/{sid}").json()["messages"]]
        self.assertEqual(texts.count("소화기 어디 있어?"), 3)

    def test_expired_session_cannot_resume(self):
        sid = self.start()
        restart_server()
        with db.connect() as conn:
            conn.execute("UPDATE sessions SET updated_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (sid,))
        self.assertEqual(self.c.get(f"/sessions/{sid}").status_code, 404)

    def test_unknown_session_404(self):
        self.assertEqual(self.c.get("/sessions/nope123").status_code, 404)

    def test_ai_calls_are_logged_with_tokens(self):
        sid = self.start()
        fake = {"verdict": "unclear", "intent": "question", "reply": "탕비실 옆!", "reason": "t",
                "model": "gemini-test", "latency_ms": 1234,
                "usage": {"promptTokenCount": 1700, "candidatesTokenCount": 80, "totalTokenCount": 1780}}
        with patch("app.ai.judge_action", return_value=fake):
            self.say(sid, "소화기 어디 있어?")
        with patch("app.ai.judge_action", return_value={"verdict": "unclear", "reply": "", "reason": "fallback"}):
            self.say(sid, "다시")
        with db.connect() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT model, input_tokens, output_tokens, latency_ms, result FROM llm_calls WHERE session_id = ? ORDER BY id", (sid,))]
        self.assertEqual(rows[0], {"model": "gemini-test", "input_tokens": 1700, "output_tokens": 80,
                                   "latency_ms": 1234, "result": "ok"})
        self.assertEqual(rows[1]["result"], "fallback")
        with patch.dict(os.environ, {"PRICE_FAST_INPUT_PER_M": "0.1", "PRICE_FAST_OUTPUT_PER_M": "0.4", "USD_TO_KRW": "1400"}):
            stats = db.scenario_stats("fire_office")
        self.assertGreaterEqual(stats["ai"]["input_tokens"], 1700)
        self.assertIsNotNone(stats["ai"]["cost_per_play_krw"])

    def test_admin_stats_come_from_db_after_restart(self):
        sid = self.start()
        for _ in range(15):
            self.say(sid, "음...")                      # 끝까지 (전부 도움받음)
        restart_server()
        row = next(r for r in self.c.get("/admin/scenarios", headers={"X-Admin-Token": "t"}).json() if r["id"] == "fire_office")
        self.assertGreaterEqual(row["stats"]["finished"], 1)
        self.assertGreaterEqual(row["stats"]["stage_fail"].get("1", 0), 1)

    def test_db_failure_does_not_break_play(self):
        sid = self.start()
        with patch("app.db.save_session", side_effect=OSError("disk full")), self.assertLogs("mia.harness", "ERROR"):
            turn = self.say(sid, "불이야! 119에 신고할게요")
        self.assertEqual(turn["stage"], 2)


if __name__ == "__main__":
    unittest.main()
