"""운영자 CMS 검증. 실제 시나리오 폴더 대신 임시 폴더를 쓰고, 실제 AI를 호출하지 않는다.

실행: python -X utf8 cms_test.py
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import harness
from app.main import app

TOKEN = "test-admin-token"
H = {"X-Admin-Token": TOKEN}


class CmsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(harness.SCENARIO_DIR / "fire_office.json", self.tmp / "fire_office.json")
        for p in [patch.dict(os.environ, {"ADMIN_TOKEN": TOKEN}), patch("app.ai._api_key", return_value=None),
                  patch.object(harness, "SCENARIO_DIR", self.tmp),
                  patch.dict(harness.SCENARIOS, {"fire_office": copy.deepcopy(harness.SCENARIOS["fire_office"])}, clear=True)]:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.c = TestClient(app)

    def create(self, sid="school_fire", title="학교 화재"):
        return self.c.post("/admin/scenarios", headers=H, json={"id": sid, "title": title, "category": "화재"})

    # ---------- 접근 제어 ----------
    def test_token_required(self):
        self.assertEqual(self.c.get("/admin/scenarios").status_code, 401)
        self.assertEqual(self.c.get("/admin/scenarios", headers={"X-Admin-Token": "wrong"}).status_code, 401)
        with patch.dict(os.environ, {"ADMIN_TOKEN": ""}):
            self.assertEqual(self.c.get("/admin/scenarios", headers=H).status_code, 503)

    def test_path_traversal_ids_rejected(self):
        for bad in ["../evil", "Fire", "a", "x" * 50, "fire-office"]:
            r = self.c.post("/admin/scenarios", headers=H, json={"id": bad, "title": "t"})
            self.assertIn(r.status_code, (400, 422), bad)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["fire_office.json"])

    # ---------- 만들기·저장·공개 ----------
    def test_create_is_draft_and_hidden_from_players(self):
        r = self.create()
        self.assertEqual(r.status_code, 201)
        self.assertTrue((self.tmp / "school_fire.json").exists())
        self.assertEqual(r.json()["scenario"]["status"], "draft")
        public_ids = [s["id"] for s in self.c.get("/scenarios").json()]
        self.assertNotIn("school_fire", public_ids)
        self.assertEqual(self.c.post("/sessions", json={"scenario_id": "school_fire"}).status_code, 404)
        # 운영자 미리 플레이는 가능
        self.assertEqual(self.c.post("/sessions", headers=H, json={"scenario_id": "school_fire"}).status_code, 200)
        self.assertEqual(self.create().status_code, 409)

    def test_save_validates_and_blocks_broken_scenario(self):
        self.create()
        sc = self.c.get("/admin/scenarios/school_fire", headers=H).json()["scenario"]
        broken = copy.deepcopy(sc)
        broken["stages"][0]["character_id"] = "nobody"
        broken["stages"][0]["rubric"] = [{"id": "x", "label": "x", "patterns": [["(괄호"]]}]
        r = self.c.put("/admin/scenarios/school_fire", headers=H, json=broken)
        self.assertEqual(r.status_code, 422)
        errors = r.json()["detail"]["errors"]
        self.assertTrue(any("캐릭터" in e for e in errors))
        self.assertTrue(any("문법" in e for e in errors))
        on_disk = json.loads((self.tmp / "school_fire.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["stages"][0]["character_id"], "partner")   # 망가진 내용은 저장되지 않음

        sc["title"] = "학교 과학실 화재"
        r = self.c.put("/admin/scenarios/school_fire", headers=H, json=sc)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads((self.tmp / "school_fire.json").read_text(encoding="utf-8"))["title"], "학교 과학실 화재")

    def test_id_cannot_change_on_save(self):
        self.create()
        sc = self.c.get("/admin/scenarios/school_fire", headers=H).json()["scenario"]
        sc["id"] = "other_id"
        self.assertEqual(self.c.put("/admin/scenarios/school_fire", headers=H, json=sc).status_code, 400)

    def test_publish_makes_it_playable(self):
        self.create()
        r = self.c.post("/admin/scenarios/school_fire/status", headers=H, json={"status": "published"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("school_fire", [s["id"] for s in self.c.get("/scenarios").json()])
        self.assertEqual(self.c.post("/sessions", json={"scenario_id": "school_fire"}).status_code, 200)
        self.c.post("/admin/scenarios/school_fire/status", headers=H, json={"status": "draft"})
        self.assertNotIn("school_fire", [s["id"] for s in self.c.get("/scenarios").json()])

    def test_duplicate_keeps_content_as_draft(self):
        r = self.c.post("/admin/scenarios/fire_office/duplicate", headers=H,
                        json={"id": "fire_school", "title": "학교 화재 대피", "category": "화재"})
        self.assertEqual(r.status_code, 201)
        sc = r.json()["scenario"]
        self.assertEqual(sc["status"], "draft")
        self.assertEqual(len(sc["stages"]), 5)
        self.assertEqual(r.json()["errors"], [])

    def test_template_scenario_plays_to_the_end(self):
        """새로 만든 1단계 뼈대도 하네스에서 끝까지 돌아야 한다."""
        self.create()
        t = self.c.post("/sessions", headers=H, json={"scenario_id": "school_fire"}).json()
        for _ in range(3):
            t = self.c.post(f"/sessions/{t['session_id']}/messages", json={"text": "음..."}).json()
        self.assertEqual(t["status"], "cleared")
        self.assertEqual(self.c.get(f"/sessions/{t['session_id']}/report").status_code, 200)

    def test_stats_count_plays(self):
        t = self.c.post("/sessions", json={"scenario_id": "fire_office"}).json()
        self.c.post(f"/sessions/{t['session_id']}/messages", json={"text": "불이야! 119에 신고할게요"})
        row = next(s for s in self.c.get("/admin/scenarios", headers=H).json() if s["id"] == "fire_office")
        self.assertGreaterEqual(row["stats"]["plays"], 1)
        self.assertEqual(row["errors"], 0)


if __name__ == "__main__":
    unittest.main()
