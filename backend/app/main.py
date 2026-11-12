"""꼬리면접 API 서버.

지금은 AI 대신 mock_ai_* 함수가 가짜 응답을 준다.
팀원 B가 app/ai.py 를 만들면 mock 함수를 실제 호출로 바꾸면 된다.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import harness
from .schemas import AnswerRequest, ItemScore, QuestionReport, Report, StartRequest, Turn

app = FastAPI(title="꼬리면접 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 가짜 AI (2주차에 실제 API 호출로 교체) ----------
def mock_ai_followup(question: dict, answer: str) -> dict:
    """답변이 짧으면 꼬리질문을 제안하는 흉내."""
    if len(answer) < 30:
        return {"need_followup": True, "utterance": "조금 더 구체적인 경험이나 예시를 들어 설명해 주시겠어요?"}
    return {"need_followup": False, "utterance": ""}


def mock_ai_report(iv: harness.Interview) -> list[QuestionReport]:
    items = []
    for q in iv.plan:
        items.append(QuestionReport(
            question_id=q["id"],
            question=q["question"],
            scores=[ItemScore(criterion=c, score=1) for c in q["rubric"]],
            evidence="(가짜 데이터) 답변에서 개념은 설명했으나 예시가 부족함",
            improvement="(가짜 데이터) 실제 프로젝트 경험을 한 가지 들어 설명해 보세요.",
        ))
    return items
# -------------------------------------------------------------


def _get(interview_id: str) -> harness.Interview:
    iv = harness.INTERVIEWS.get(interview_id)
    if not iv:
        raise HTTPException(404, "면접을 찾을 수 없습니다.")
    return iv


@app.post("/interviews", response_model=Turn)
def start_interview(req: StartRequest):
    iv = harness.create_interview(req.job, req.cover_letter)
    return Turn(interview_id=iv.id, type="main",
                question=harness.current_question(iv)["question"], progress=harness.progress(iv))


@app.post("/interviews/{interview_id}/answers", response_model=Turn)
def submit_answer(interview_id: str, req: AnswerRequest):
    iv = _get(interview_id)
    if iv.finished:
        raise HTTPException(400, "이미 끝난 면접입니다.")
    suggestion = mock_ai_followup(harness.current_question(iv), req.answer)
    kind, question = harness.submit_answer(iv, req.answer, suggestion)
    return Turn(interview_id=iv.id, type=kind, question=question, progress=harness.progress(iv))


@app.get("/interviews/{interview_id}/report", response_model=Report)
def get_report(interview_id: str):
    iv = _get(interview_id)
    if not iv.finished:
        raise HTTPException(400, "면접이 아직 끝나지 않았습니다.")
    questions = mock_ai_report(iv)
    total = sum(s.score for q in questions for s in q.scores)
    max_score = sum(2 * len(q.scores) for q in questions)
    return Report(interview_id=iv.id, total_score=total, max_score=max_score, questions=questions)
