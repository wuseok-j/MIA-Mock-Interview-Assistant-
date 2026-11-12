# API 명세 v0.1

기본 주소: `http://localhost:8000`
서버 실행 후 `http://localhost:8000/docs` 에서 직접 테스트할 수 있다.
형식을 바꿀 때는 이 문서와 `backend/app/schemas.py` 를 함께 수정하고 팀에 공유한다.

---

## 1. 면접 시작 `POST /interviews`

요청
```json
{ "job": "backend_junior", "cover_letter": "저는 ... (최대 2,000자, 생략 가능)" }
```
응답
```json
{ "interview_id": "a1b2c3d4e5f6", "type": "main", "question": "데이터베이스 인덱스를 ...", "progress": "1/5" }
```

## 2. 답변 제출 `POST /interviews/{interview_id}/answers`

요청
```json
{ "answer": "조회가 빨라져서 썼습니다. (1~1,000자)" }
```
응답 – `type` 에 따라 화면 처리
- `"followup"`: 꼬리질문 표시 (같은 메인 질문 안에서 최대 2회)
- `"main"`: 다음 메인 질문 표시
- `"finished"`: 리포트 화면으로 이동 (`question` 은 null)

```json
{ "interview_id": "a1b2c3d4e5f6", "type": "followup", "question": "조금 더 구체적인 경험이나 ...", "progress": "1/5" }
```

## 3. 리포트 조회 `GET /interviews/{interview_id}/report`

응답
```json
{
  "interview_id": "a1b2c3d4e5f6",
  "total_score": 15,
  "max_score": 30,
  "questions": [
    {
      "question_id": "db-001",
      "question": "데이터베이스 인덱스를 ...",
      "scores": [
        { "criterion": "개념 설명", "score": 1 },
        { "criterion": "장단점(쓰기 성능 등)", "score": 0 },
        { "criterion": "실제 사용 예시", "score": 1 }
      ],
      "evidence": "답변에서 ...",
      "improvement": "쓰기 성능 저하 등 단점도 ..."
    }
  ]
}
```

## 오류 응답

| 코드 | 상황 | 화면 처리 |
|---|---|---|
| 400 | 끝난 면접에 답변 / 안 끝난 면접 리포트 요청 | 안내 문구 표시 |
| 404 | 없는 면접 id | 처음 화면으로 이동 |
| 422 | 빈 답변, 글자수 초과 | 입력창 아래 안내 문구 |
| 500·502 | 서버·AI 오류 | ‘다시 시도’ 버튼 (작성한 답변 유지) |
