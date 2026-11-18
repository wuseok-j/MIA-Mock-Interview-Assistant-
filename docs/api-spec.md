# API 명세 v0.4 (재난·안전 롤플레잉)

기본 주소: `http://localhost:8000`
서버 실행 후 `http://localhost:8000/docs` 에서 직접 눌러 볼 수 있다.
형식을 바꿀 때는 이 문서와 `backend/app/schemas.py` 를 함께 수정하고 팀에 공유한다.

화면 흐름: **① 시나리오 목록 → ② 임무 브리핑 → ③ 채팅 플레이 → ④ 판단 복기**

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

## v0.3 추가 필드

- 리포트 checks에 `user_actions: list[str]`(해당 단계 실제 발언), `attempts: int`(필터 통과 후 판단 시도 수)를 추가한다. 차단 입력은 발언 근거에서 제외한다.
- 화면 흐름은 목록 → 브리핑 → 플레이 → 리포트다. 브리핑 확인 전에는 세션을 생성하지 않는다.
- 자동 판정의 근거를 표시하며 안전 역량 인증으로 표현하지 않는다.

## v0.4 선택의 영향과 근거 기반 복기

기존 필드는 유지하며 아래 필드를 추가한다.

| 응답 | 필드 | 의미 |
|---|---|---|
| ScenarioSummary | `briefing: {role, mission, focus}` | 공개 가능한 역할·목표·연습 역량. 판정 정규식은 비공개 |
| Turn | `conditions: string[]` | 앞선 단계의 확인·도움 이력 표시 |
| Turn | `attempts_left: int` | 현재 단계의 남은 판단 기회, 종료 시 0 |
| CheckResult | `evidence: Evidence[]` | 행동 항목별 확인 여부·실제 발언·근거 출처 |
| Report | `timeline: Decision[]` | 평가된 입력별 판정·위험도 변화·결과 |
| Report | `conditions: string[]` | 최종 선택 이력 |
| Report | `review_points: string[]` | 미충족·미도달 단계 제목 |

`Evidence`: `{id, label, met: bool, quote: string, sources: [{name, url}]}`. 미확인 quote는 빈 문자열이다.

`Decision`: `{stage, title, action, verdict, risk_before, risk_after, outcome}`. verdict는 기존 correct/wrong/unclear다. 입력 차단과 AI 장애는 타임라인과 판단 횟수에서 제외한다.

여러 발언에서 확인한 행동을 단계별로 누적한다. 위험 행동이 판정되면 그 단계의 근거를 초기화하고 위험도를 올린다. 모든 필수 행동을 확인해야 통과하며, 기회가 소진되면 실패 기록과 도움받는 전개를 남긴다. `cleared`는 건물 밖 도착을 의미하며 모든 행동 통과를 뜻하지 않는다.

현재는 JSON의 제한된 표현 패턴으로 근거를 검증한다. 미등록 표현·복잡한 부정·인용은 오판할 수 있다. 상세 한계와 시연 방법은 [설계 문서](decision-design.md)를 따른다.

## v0.5 운영자 CMS `/admin/...`

모든 요청에 헤더 `X-Admin-Token: <.env 의 ADMIN_TOKEN>` 필요. ADMIN_TOKEN 이 비어 있으면 503, 토큰이 틀리면 401.

| 요청 | 하는 일 |
|---|---|
| `GET /admin/scenarios` | 전체 시나리오(작성 중 포함) 요약: status, 검사 오류·경고 수, 이용 현황 `stats{plays, finished, cleared, avg_passed, stage_fail}` |
| `GET /admin/scenarios/{id}` | 시나리오 전체 JSON(정답·행동 기준 포함) + `errors`, `warnings`, `stats` |
| `POST /admin/scenarios` `{id, title, category}` | 1단계 뼈대로 새로 만들기 (status=draft). id 는 `^[a-z][a-z0-9_]{2,39}$`, 중복이면 409 |
| `POST /admin/scenarios/{id}/duplicate` `{id, title, category}` | 기존 시나리오 복제 (draft) |
| `PUT /admin/scenarios/{id}` 시나리오 JSON | 검사 후 저장. 오류가 있으면 422 `{detail: {message, errors, warnings}}` 이고 저장하지 않음. id 변경 불가 |
| `POST /admin/scenarios/{id}/status` `{status: "draft"|"published"}` | 공개/비공개. 공개는 검사 오류 0개일 때만 |
| `POST /admin/validate` 시나리오 JSON | 저장 없이 검사만 → `{errors, warnings}` |

이용자 API 변화: `GET /scenarios` 는 `status=published`(없으면 published 로 간주)만 보여 준다. 작성 중 시나리오는 `GET /scenarios/{id}`·`POST /sessions` 에 운영자 토큰 헤더가 있을 때만 열린다 (미리 플레이).
