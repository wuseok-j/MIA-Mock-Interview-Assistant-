"""프론트와 주고받는 데이터 형식. 바꿀 때는 docs/api-spec.md 도 같이 수정한다."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    job: Literal["backend_junior"] = "backend_junior"
    cover_letter: str = Field("", max_length=2000)


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=1000)


class Turn(BaseModel):
    """면접관이 다음에 할 말."""
    interview_id: str
    type: Literal["main", "followup", "finished"]
    question: Optional[str] = None
    progress: str  # 예: "3/5"


class ItemScore(BaseModel):
    criterion: str
    score: int = Field(..., ge=0, le=2)


class QuestionReport(BaseModel):
    question_id: str
    question: str
    scores: list[ItemScore]
    evidence: str
    improvement: str


class Report(BaseModel):
    interview_id: str
    total_score: int
    max_score: int
    questions: list[QuestionReport]
