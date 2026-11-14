"""프론트와 주고받는 데이터 형식. 바꿀 때는 docs/api-spec.md 도 같이 수정한다."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str
    role: str
    image: Optional[str] = None


class ScenarioSummary(BaseModel):
    """시나리오 카드. 정답 정보는 들어 있지 않다."""
    id: str
    title: str
    summary: str
    category: str
    thumbnail: Optional[str] = None
    estimated_minutes: Optional[int] = None
    total_stages: int
    characters: list[Character]


class StartRequest(BaseModel):
    scenario_id: str = Field(..., max_length=50)


class MessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


class Message(BaseModel):
    role: Literal["narrator", "character", "user", "system"]
    name: str
    text: str


class Turn(BaseModel):
    """한 턴의 결과: 새로 보여줄 메시지들 + 현재 상태."""
    session_id: str
    messages: list[Message]
    stage: int            # 현재 단계 번호 (1부터)
    stage_title: str
    total_stages: int
    risk: int
    max_risk: int
    image: Optional[str] = None
    status: Literal["playing", "cleared", "failed"]


class CheckResult(BaseModel):
    id: str
    stage: int
    stage_title: str
    criterion: str
    result: Literal["correct", "failed", "not_reached"]
    correct_action: str
    comment: str


class Source(BaseModel):
    name: str
    url: str


class Report(BaseModel):
    session_id: str
    scenario_title: str
    status: Literal["cleared", "failed"]
    risk: int
    max_risk: int
    passed: int
    total: int
    summary: str
    checks: list[CheckResult]
    sources: list[Source]
