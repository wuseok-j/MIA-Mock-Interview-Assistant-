# frontend — 웹 프로토타입 (React + Vite)

화면 3개: ① 시나리오 목록 → ② 채팅 플레이 → ③ 종료 리포트

## 실행

백엔드를 먼저 켠다 (터미널 1):
```bash
cd backend
.venv\Scripts\activate        # Mac: source .venv/bin/activate
uvicorn app.main:app --reload
```

프론트를 켠다 (터미널 2):
```bash
cd frontend
npm install                   # 처음 한 번만
npm run dev
```
브라우저에서 http://localhost:5173 열기.

## 파일 구조

| 파일 | 하는 일 |
|---|---|
| `src/App.jsx` | 화면 3개 전환 (라우터 없이 상태값 하나로) |
| `src/api.js` | 서버 호출 모음. 형식은 `docs/api-spec.md` |
| `src/pages/ScenarioList.jsx` | ① 시나리오 카드 목록 |
| `src/pages/Play.jsx` | ② 채팅 플레이: 단계 표시, 위험도 게이지, 장면 패널, 말풍선, 입력창 |
| `src/pages/Report.jsx` | ③ 단계별 통과/실패, 피드백, 올바른 행동, 출처 |
| `src/styles.css` | 전체 스타일. 맨 위 `:root` 색만 바꿔도 톤이 바뀐다 |
| `vite.config.js` | `/api/...` 요청을 백엔드(8000번)로 넘기는 설정 |

## 알아 둘 점

- 화면은 **서버가 준 값만 보여 준다.** 단계·위험도·종료 여부를 화면에서 계산하지 않는다 (하네스 원칙).
- 장면 이미지(`turn.image`)는 아직 없어서 이모지 + 단계 이름으로 대신한다. 이미지가 준비되면 `Play.jsx` 의 장면 패널에서 바꾸면 된다.
- 서버 오류가 나면 입력한 문장은 지워지지 않고 입력창에 남는다.
