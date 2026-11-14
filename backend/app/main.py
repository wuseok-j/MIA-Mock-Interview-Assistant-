"""재난·안전 롤플레잉 API 서버.

이 파일은 '요청을 받고 응답 형식을 맞추는' 일만 한다.
진행 규칙은 harness.py, AI 호출은 ai.py, 입력 필터는 safety.py 에 있다.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import harness
from .schemas import MessageRequest, Report, ScenarioSummary, StartRequest, Turn

app = FastAPI(title="MIA 재난·안전 롤플레잉 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get(session_id: str) -> harness.Session:
    s = harness.SESSIONS.get(session_id)
    if not s:
        raise HTTPException(404, "플레이 기록을 찾을 수 없습니다.")
    return s


def _turn(s: harness.Session, messages: list[dict]) -> Turn:
    st = harness.current_stage(s)
    return Turn(
        session_id=s.id, messages=messages,
        stage=st["stage"], stage_title=st["title"], total_stages=len(s.scenario["stages"]),
        risk=s.risk, max_risk=s.scenario["max_risk"], image=st.get("image"), status=s.status,
    )


@app.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios():
    return [harness.public_scenario(sc) for sc in harness.SCENARIOS.values()]


@app.get("/scenarios/{scenario_id}", response_model=ScenarioSummary)
def get_scenario(scenario_id: str):
    sc = harness.SCENARIOS.get(scenario_id)
    if not sc:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    return harness.public_scenario(sc)


@app.post("/sessions", response_model=Turn)
def start_session(req: StartRequest):
    if req.scenario_id not in harness.SCENARIOS:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    s, messages = harness.create_session(req.scenario_id)
    return _turn(s, messages)


@app.post("/sessions/{session_id}/messages", response_model=Turn)
def send_message(session_id: str, req: MessageRequest):
    s = _get(session_id)
    if s.status != "playing":
        raise HTTPException(400, "이미 끝난 플레이입니다.")
    messages = harness.handle_message(s, req.text)
    return _turn(s, messages)


@app.get("/sessions/{session_id}/report", response_model=Report)
def get_report(session_id: str):
    s = _get(session_id)
    if s.status == "playing":
        raise HTTPException(400, "플레이가 아직 끝나지 않았습니다.")
    return harness.build_report(s)
