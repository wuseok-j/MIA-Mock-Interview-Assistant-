"""AI 호출 모음 (담당: 김채희).

서버(main.py, harness.py)는 이 파일의 함수 3개만 부른다.
함수 이름·입력·반환 형식은 팀 합의 사항이므로, 바꿀 때는 장우석과 먼저 이야기한다.

지금은 가짜 응답을 돌려준다. 각 함수 안의 TODO 부분을 실제 API 호출로 바꾸면 된다.
- 진행(질문 생성·꼬리질문): 경량 모델  LLM_MODEL_FAST
- 평가 리포트: 상위 모델            LLM_MODEL_SMART
- 프롬프트 문장은 prompts.py 에 따로 둔다.
- 실패 처리: 1회 재시도 → JSON 형식 오류 시 재요청 → 2회 실패 시 아래 fallback 값 반환
"""
from __future__ import annotations


def generate_cover_letter_questions(cover_letter: str, n: int = 2) -> list[dict]:
    """자기소개서를 근거로 면접 질문 n개를 만든다.

    반환: 질문은행과 같은 형식의 dict 목록
        [{"id": "cl-001", "category": "자기소개서",
          "question": "...", "rubric": ["항목1", "항목2", "항목3"]}, ...]
    자기소개서가 비었거나 생성에 실패하면 [] 를 반환한다.
    (빈 목록이면 서버가 질문은행에서 5개를 모두 뽑는다.)
    """
    # TODO(김채희): 실제 API 호출로 교체
    return []


def judge_followup(question: dict, answer: str, history: list[dict]) -> dict:
    """답변을 보고 꼬리질문이 필요한지 판단한다.

    question: 현재 메인 질문 (질문은행 항목 형식)
    answer:   지원자의 이번 답변
    history:  이 메인 질문에서 오간 대화 [{"role": "interviewer"|"candidate", "text": "..."}]
    반환: {"need_followup": bool, "utterance": str}
        need_followup 이 False 이면 utterance 는 "".
    꼬리질문 횟수 제한(최대 2회)은 서버가 강제하므로 여기서 신경 쓰지 않아도 된다.
    실패 시 {"need_followup": False, "utterance": ""} 를 반환한다. (다음 질문으로 넘어감)
    """
    # TODO(김채희): 실제 API 호출로 교체. 아래는 가짜 응답.
    if len(answer) < 30:
        return {"need_followup": True,
                "utterance": "조금 더 구체적인 경험이나 예시를 들어 설명해 주시겠어요?"}
    return {"need_followup": False, "utterance": ""}


def evaluate(plan: list[dict], transcript: list[dict]) -> list[dict]:
    """면접 전체를 루브릭 기준으로 평가한다.

    plan:       메인 질문 목록 (질문은행 항목 형식)
    transcript: 전체 대화 [{"question_id", "role", "text"}]
    반환: 질문마다 1개씩
        [{"question_id": "db-001",
          "scores": [{"criterion": "개념 설명", "score": 0~2}, ...],   # rubric 순서·개수 그대로
          "evidence": "점수의 근거",
          "improvement": "개선점"}, ...]
    점수 범위(0~2)·개수 검증은 서버가 다시 한다. 범위를 벗어나면 서버가 재평가를 요청한다.
    """
    # TODO(김채희): 실제 API 호출로 교체. 아래는 가짜 응답.
    return [
        {
            "question_id": q["id"],
            "scores": [{"criterion": c, "score": 1} for c in q["rubric"]],
            "evidence": "(가짜 데이터) 답변에서 개념은 설명했으나 예시가 부족함",
            "improvement": "(가짜 데이터) 실제 프로젝트 경험을 한 가지 들어 설명해 보세요.",
        }
        for q in plan
    ]
