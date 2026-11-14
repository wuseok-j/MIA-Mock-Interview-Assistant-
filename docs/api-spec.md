# API 명세 v0.2 (재난·안전 롤플레잉)

기본 주소: `http://localhost:8000`
서버 실행 후 `http://localhost:8000/docs` 에서 직접 눌러 볼 수 있다.
형식을 바꿀 때는 이 문서와 `backend/app/schemas.py` 를 함께 수정하고 팀에 공유한다.

화면 흐름: **① 시나리오 목록 → ② 채팅 플레이 → ③ 종료 리포트**

---

## 1. 시나리오 목록 `GET /scenarios`

응답 (정답 정보는 포함되지 않음)
```json
[
  {
    "id": "fire_office",
    "title": "오피스 화재 대피",
    "summary": "근무 중인 7층 사무실 탕비실에서 연기가 난다. ...",
    "category": "화재",
    "thumbnail": "fire_office/thumbnail.png",
    "estimated_minutes": 7,
    "total_stages": 5,
    "characters": [{ "name": "박지훈", "role": "옆자리 동료 (입사 2년 차)", "image": "fire_office/jihoon.png" }]
  }
]
```

`GET /scenarios/{id}` 는 위 항목 하나를 돌려준다.

## 2. 플레이 시작 `POST /sessions`

요청
```json
{ "scenario_id": "fire_office" }
```
응답 = **Turn** (아래 3번과 같은 형식). 첫 단계의 상황 설명과 캐릭터 첫 대사가 `messages` 에 들어 있다.

## 3. 이용자 발언 `POST /sessions/{session_id}/messages`

요청
```json
{ "text": "불이야! 비상벨 누르고 119에 신고할게요 (1~300자)" }
```
응답 – Turn
```json
{
  "session_id": "a1b2c3d4e5f6",
  "messages": [
    { "role": "user",      "name": "나",     "text": "불이야! ..." },
    { "role": "character", "name": "박지훈", "text": "헉, 진짜 불이야? ..." },
    { "role": "narrator",  "name": "상황",   "text": "비상벨이 울리고 ..." },
    { "role": "character", "name": "박지훈", "text": "엘리베이터 금방 온다! ..." }
  ],
  "stage": 2,
  "stage_title": "엘리베이터 앞",
  "total_stages": 5,
  "risk": 0,
  "max_risk": 6,
  "image": "fire_office/stage2_elevator.png",
  "status": "playing"
}
```

`messages` 는 **이번 턴에 새로 생긴 메시지만** 들어 있다. 화면은 기존 채팅 아래에 이어 붙이면 된다.

| role | 화면 표시 |
|---|---|
| `user` | 오른쪽 말풍선 (내 말) |
| `character` | 왼쪽 말풍선 + 캐릭터 이름·프로필 |
| `narrator` | 가운데 회색 상황 설명 (장면 이미지 옆) |
| `system` | 가운데 안내 박스 (안전 필터 안내, 종료 안내) |

| status | 화면 처리 |
|---|---|
| `playing` | 계속 입력 받기 |
| `cleared` / `failed` | 입력창 잠그고 '리포트 보기' 버튼 |

`risk / max_risk` 는 위험도 게이지로 보여 준다. `image` 가 바뀌면 장면 이미지를 바꾼다.

## 4. 리포트 `GET /sessions/{session_id}/report`

```json
{
  "session_id": "a1b2c3d4e5f6",
  "scenario_title": "오피스 화재 대피",
  "status": "cleared",
  "risk": 2,
  "max_risk": 6,
  "passed": 4,
  "total": 5,
  "summary": "총평 2~3문장",
  "checks": [
    {
      "id": "c2",
      "stage": 2,
      "stage_title": "엘리베이터 앞",
      "criterion": "엘리베이터 대신 계단으로 대피했다",
      "result": "correct",
      "correct_action": "엘리베이터는 ... 비상계단으로 대피한다.",
      "comment": "이 항목 피드백"
    }
  ],
  "sources": [{ "name": "국민재난안전포털 – 화재 국민행동요령", "url": "https://www.safekorea.go.kr" }]
}
```
`result`: `correct`(통과) / `failed`(실패) / `not_reached`(도달 못 함)

## 오류 응답

| 코드 | 상황 | 화면 처리 |
|---|---|---|
| 400 | 끝난 플레이에 발언 / 안 끝난 플레이의 리포트 요청 | 안내 문구 |
| 404 | 없는 시나리오·세션 id | 시나리오 목록으로 이동 |
| 422 | 빈 입력, 300자 초과 | 입력창 아래 안내 문구 |
| 500·502 | 서버·AI 오류 | '다시 시도' 버튼 (입력한 문장 유지) |
