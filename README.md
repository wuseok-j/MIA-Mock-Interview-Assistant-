# 꼬리면접 🎤

신입 백엔드 개발자를 위한 AI 모의면접 서비스.
직무와 자기소개서를 입력하면 AI 면접관이 메인 질문 5개와 답변에 따른 꼬리질문으로 면접을 진행하고, 끝나면 질문별 평가 리포트를 보여준다.

## 폴더 구조

| 폴더 | 내용 | 담당 |
|---|---|---|
| `frontend/` | React 화면 (설정 · 면접 · 리포트) | 팀원 A |
| `backend/app/` | FastAPI 서버, 면접 상태 관리(하네스) | 팀원 C |
| `backend/app/prompts.py` | AI 프롬프트 | 팀원 B |
| `backend/first_run.py` | 1주차 API 첫 실행 확인 스크립트 | 팀원 B |
| `data/` | 질문은행 · 루브릭 JSON | 팀원 D |
| `docs/` | 수행계획서, API 명세, 회의록 | 전원 |

## 처음 받았을 때

```bash
git clone <레포 주소>
cd kkori-interview
cp .env.example .env          # .env 에 API 키 입력 (Windows: copy .env.example .env)

cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1주차 첫 실행 확인
```bash
python first_run.py
```
면접 질문 1개와 토큰 사용량·예상 비용이 출력되면 성공. 결과를 캡처해 주간 점검에 사용한다.

### 서버 실행 (현재는 가짜 데이터 응답)
```bash
uvicorn app.main:app --reload
```
브라우저에서 http://localhost:8000/docs 를 열면 API를 직접 눌러볼 수 있다.

## 협업 규칙

1. `main` 브랜치에는 직접 push 하지 않는다. 기능별 브랜치에서 작업 후 PR로 합친다.
   - 브랜치 이름: `feat/면접화면`, `fix/리포트오류`, `docs/api명세` 처럼 `종류/내용`
2. PR은 팀원 1명 이상 확인 후 머지한다.
3. 할 일은 GitHub Issues에 올리고, Projects 보드에서 진행 상태를 관리한다.
4. **API 키 등 비밀 정보는 절대 커밋하지 않는다.** 실수로 올렸다면 즉시 팀에 알리고 키를 폐기·재발급한다.
5. 프론트·백엔드가 주고받는 형식은 `docs/api-spec.md`, 질문은행 형식은 `data/question_bank.json`을 기준으로 한다. 바꿀 때는 문서부터 수정하고 공유한다.
