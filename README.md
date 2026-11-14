# MIA — 재난·안전 대응 롤플레잉 🚒

> **문제:** 안전교육은 대부분 영상 시청이라, 실제 상황에서 판단해 보는 연습을 할 수 없다.
> **해결:** 화재·지진 등 상황 속 인물과 채팅하며 직접 판단하고, 행동별 피드백을 받는다.

운영자(교사·기업 안전 담당자)가 재난 시나리오를 올리고, 이용자(학생·직원)가 시나리오 속 인물과 채팅하며 판단해 본 뒤, 끝나면 행동별 평가 리포트를 받는 생성형 AI 서비스.

## 구조

```
[이용자 웹] ─┐
             ├─> [백엔드 API] ─> [하네스] ─> [LLM API]
[운영자 CMS] ┘        │             │
                    [DB] <──────────┘
```

**하네스 원칙:** 진행 상태(단계·위험도·시도 횟수)는 모델이 아니라 **서버가 쥔다.**
모델은 "캐릭터 대사"와 "행동 판정 제안"만 만들고, 단계 이동은 서버가 시나리오 규칙으로 결정한다.

## 폴더 구조

| 위치 | 내용 |
|---|---|
| `backend/app/harness.py` | 하네스: 단계 진행·위험도·판정 검증 (핵심) |
| `backend/app/ai.py` | AI 호출 (지금은 가짜 AI, 실제 호출로 교체 예정) |
| `backend/app/safety.py` | 인젝션·부적절 표현 1차 필터 |
| `backend/app/main.py`, `schemas.py` | API 서버, 요청·응답 형식 |
| `backend/play_test.py` | 시나리오 자동 플레이 테스트 |
| `data/scenarios/` | 시나리오 JSON + [작성 가이드](data/scenarios/README.md) |
| `docs/api-spec.md` | 프론트 ↔ 백엔드 API 명세 |
| `docs/research/` | 유사 서비스·시장 조사 |
| `docs/tasks/` | **팀원별 할 일** |
| `frontend/` | React 화면 (예정) |

## 처음 받았을 때

```bash
git clone https://github.com/wuseok-j/MIA-Mock-Interview-Assistant-.git
cd MIA-Mock-Interview-Assistant-
cp .env.example .env          # .env 에 API 키 입력 (Windows: copy .env.example .env)

cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 하네스 동작 확인 (API 키 없어도 됨)
```bash
python play_test.py
```
모범 플레이 / 인젝션 시도 / 위험한 플레이 3가지가 자동으로 돌고 `✅` 가 나오면 성공.

### 서버 실행
```bash
uvicorn app.main:app --reload
```
http://localhost:8000/docs 에서 `POST /sessions` → `POST /sessions/{id}/messages` 순서로 직접 플레이할 수 있다.

### 실제 AI 첫 호출 확인
```bash
python first_run.py
```
캐릭터 대사 1개와 토큰 사용량·예상 비용이 출력되면 성공.

## 협업 규칙

1. `main` 브랜치에는 직접 push 하지 않는다. 기능별 브랜치에서 작업 후 PR로 합친다.
   - 브랜치 이름: `feat/채팅화면`, `content/지진시나리오`, `docs/서비스조사` 처럼 `종류/내용`
2. **PR 승인·머지는 장우석만 한다.** (`main` 보호 규칙 + `.github/CODEOWNERS`) PR을 올리면 단톡에 링크를 남긴다.
3. **API 키 등 비밀 정보는 절대 커밋하지 않는다. AI 채팅창에도 붙여넣지 않는다.** 실수로 올렸다면 즉시 팀에 알리고 키를 폐기·재발급한다.
4. 프론트·백엔드 형식은 `docs/api-spec.md`, 시나리오 형식은 `data/scenarios/README.md` 가 기준이다. 바꿀 때는 문서부터 수정하고 공유한다.
5. 깃은 GitHub Desktop 사용. 충돌이 나면 혼자 해결하지 말고 장우석에게.
