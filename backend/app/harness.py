"""하네스: 면접 진행 상태는 모델이 아니라 서버가 관리한다.

모델은 '꼬리질문이 필요한가 / 무슨 말을 할까'만 제안하고,
다음 질문으로 넘어갈지는 이 파일의 규칙(최대 꼬리질문 횟수 등)이 결정한다.
"""
import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path

MAIN_QUESTIONS = 5
MAX_FOLLOWUP = 2
DATA = Path(__file__).resolve().parents[2] / "data" / "question_bank.json"


@dataclass
class Interview:
    id: str
    job: str
    cover_letter: str
    plan: list[dict]                      # 메인 질문 5개 (질문은행 항목 형식)
    current_index: int = 0
    followup_count: int = 0
    transcript: list[dict] = field(default_factory=list)  # {question_id, role, text}
    finished: bool = False


# TODO(팀원 C): 2주차에 SQLite 로 교체
INTERVIEWS: dict[str, Interview] = {}


def load_bank() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))["questions"]


def create_interview(job: str, cover_letter: str) -> Interview:
    bank = load_bank()
    # TODO(팀원 B): 자기소개서 기반 질문 2개를 AI로 생성해 plan 앞에 추가
    plan = random.sample(bank, k=min(MAIN_QUESTIONS, len(bank)))
    iv = Interview(id=uuid.uuid4().hex[:12], job=job, cover_letter=cover_letter, plan=plan)
    INTERVIEWS[iv.id] = iv
    _log(iv, "interviewer", plan[0]["question"])
    return iv


def current_question(iv: Interview) -> dict:
    return iv.plan[iv.current_index]


def progress(iv: Interview) -> str:
    return f"{min(iv.current_index + 1, len(iv.plan))}/{len(iv.plan)}"


def submit_answer(iv: Interview, answer: str, ai_suggestion: dict) -> tuple[str, str | None]:
    """답변을 기록하고 다음 행동을 결정한다.

    ai_suggestion 예: {"need_followup": true, "utterance": "어떤 컬럼에 인덱스를 걸었나요?"}
    반환: (type, question)  type 은 "main" | "followup" | "finished"
    """
    _log(iv, "candidate", answer)

    wants_followup = bool(ai_suggestion.get("need_followup")) and ai_suggestion.get("utterance")
    if wants_followup and iv.followup_count < MAX_FOLLOWUP:      # 서버가 횟수 제한을 강제
        iv.followup_count += 1
        _log(iv, "interviewer", ai_suggestion["utterance"])
        return "followup", ai_suggestion["utterance"]

    iv.current_index += 1
    iv.followup_count = 0
    if iv.current_index >= len(iv.plan):
        iv.finished = True
        return "finished", None

    q = current_question(iv)["question"]
    _log(iv, "interviewer", q)
    return "main", q


def _log(iv: Interview, role: str, text: str) -> None:
    qid = iv.plan[min(iv.current_index, len(iv.plan) - 1)]["id"]
    iv.transcript.append({"question_id": qid, "role": role, "text": text})
