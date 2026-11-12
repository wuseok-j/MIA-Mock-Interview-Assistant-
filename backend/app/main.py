"""꼬리면접 API 서버.

AI 호출은 모두 app/ai.py 를 거친다. (지금은 ai.py 가 가짜 응답을 준다)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import ai, harness
from .schemas import AnswerRequest, ItemScore, QuestionReport, Report, StartRequest, Turn

app = FastAPI(title="꼬리면접 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_report(iv: harness.Interview) -> list[QuestionReport]:
    """ai.evaluate 결과를 화면용 형식으로 바꾼다.
    TODO(장우석): 점수 범위·항목 수 검증, 실패 시 재평가 요청
    """
    by_id = {r["question_id"]: r for r in ai.evaluate(iv.plan, iv.transcript)}
    items = []
    for q in iv.plan:
        r = by_id[q["id"]]
        items.append(QuestionReport(
            question_id=q["id"],
            question=q["question"],
            scores=[ItemScore(**s) for s in r["scores"]],
            evidence=r["evidence"],
            improvement=r["improvement"],
        ))
    return items


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
    q = harness.current_question(iv)
    history = [t for t in iv.transcript if t["question_id"] == q["id"]]
    suggestion = ai.judge_followup(q, req.answer, history)
    kind, question = harness.submit_answer(iv, req.answer, suggestion)
    return Turn(interview_id=iv.id, type=kind, question=question, progress=harness.progress(iv))


@app.get("/interviews/{interview_id}/report", response_model=Report)
def get_report(interview_id: str):
    iv = _get(interview_id)
    if not iv.finished:
        raise HTTPException(400, "면접이 아직 끝나지 않았습니다.")
    questions = _build_report(iv)
    total = sum(s.score for q in questions for s in q.scores)
    max_score = sum(2 * len(q.scores) for q in questions)
    return Report(interview_id=iv.id, total_score=total, max_score=max_score, questions=questions)
