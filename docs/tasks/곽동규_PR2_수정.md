# 곽동규 — PR #2 수정 작업 지시서

> **사람(곽동규)에게:** AI 도구(Claude Code / Codex)에게
> "`docs/tasks/곽동규_PR2_수정.md` 읽고 그대로 수행해줘" 라고 하면 된다.
> 끝나면 단톡에 "PR #2 수정했어"라고 남기기. 중간에 막히면 화면 캡처해서 장우석에게.

---

## AI 도구에게: 배경

- 저장소: `wuseok-j/MIA-Mock-Interview-Assistant-`, 기본 브랜치 `main` (보호됨 — 직접 push 불가, PR로만 머지)
- 대상: **PR #2**, 브랜치 **`docs/agent-handoff`** (작성자 곽동규). 이 브랜치를 수정해 같은 PR에 반영한다. **새 PR을 만들지 않는다.**
- PR #2는 공용 인수인계 파일 `NEXT_STEPS.md` 를 추가하고 `CLAUDE.md` 를 수정했다.
  팀 결정: 공용 파일 하나를 4명이 고치면 충돌이 반복되므로 **사람별 파일 `docs/handoff/본인이름.md`** 로 바꾼다.
  이 규칙은 리더가 이미 `main` 의 `CLAUDE.md`("0. 작업 인수인계")와 `docs/handoff/README.md` 에 넣었다.
- `CLAUDE.md` 는 리더만 수정한다. 이 작업에서도 `CLAUDE.md` 는 `main` 버전과 **완전히 같게** 만든다.

## 목표 상태 (작업이 끝났을 때)

`git diff --stat origin/main...HEAD` 결과에 **아래 파일만** 있어야 한다.

| 파일 | 상태 |
|---|---|
| `AGENTS.md` | 신규 (아래 3단계 내용) |
| `docs/handoff/곽동규.md` | 신규 (아래 4단계 내용) |
| `docs/tasks/곽동규_PR2_수정.md` | 삭제 (이 지시서) |

`CLAUDE.md`, `NEXT_STEPS.md` 는 diff에 **나오면 안 된다.**

---

## 작업 순서

### 0. 사전 확인 (조건이 안 맞으면 중단하고 사용자에게 보고)

```bash
git status --short          # 미커밋 변경이 있으면 중단하고 사용자에게 무엇인지 보고
git fetch origin
git log origin/main --oneline -- docs/handoff/README.md   # 결과가 비어 있으면 중단: "리더의 handoff 규칙 PR이 아직 main에 머지되지 않았다"
```

### 1. 브랜치로 이동하고 main 합치기

```bash
git checkout docs/agent-handoff
git pull origin docs/agent-handoff
git merge origin/main
```

- `CLAUDE.md` 에서 충돌이 날 수 있다. **main 쪽 내용으로 해결**한다:
  ```bash
  git checkout origin/main -- CLAUDE.md
  git add CLAUDE.md
  git commit --no-edit
  ```
- `CLAUDE.md` 외의 파일에서 충돌이 나면 임의로 해결하지 말고 `git merge --abort` 후 사용자에게 보고한다.

### 2. CLAUDE.md 를 main 과 똑같이

충돌이 없었더라도 PR의 `CLAUDE.md` 수정이 남아 있을 수 있으므로 되돌린다.

```bash
git checkout origin/main -- CLAUDE.md
git diff origin/main -- CLAUDE.md     # 출력이 비어 있어야 한다
```

### 3. AGENTS.md 를 아래 내용으로 교체

```markdown
# 프로젝트 작업 지침

이 지침은 이 저장소에만 적용한다.

- 작업을 시작하기 전에 저장소 루트의 `CLAUDE.md` 를 읽고, 이 프로젝트의 작업 지침과 배경 정보로 적용한다. (Codex에서도 `AGENTS.md` 에 포함된 지침처럼 취급한다)
- 이어서 `CLAUDE.md` 의 "0. 작업 인수인계" 규칙에 따라 `docs/handoff/본인이름.md` 를 읽고, 작업을 마칠 때 같은 파일을 갱신한다.
- 프로젝트 배경과 협업 규칙의 원본은 `CLAUDE.md` 다. 여기에 내용을 복제하지 않는다.
- 사용자의 현재 명시적 요청이 문서의 과거 내용과 다르면 현재 요청을 우선한다. 실제 구현 상태는 관련 코드와 문서에서 확인한다.
```

### 4. NEXT_STEPS.md → docs/handoff/곽동규.md

```bash
git mv NEXT_STEPS.md docs/handoff/곽동규.md
```

그다음 내용을 `docs/handoff/README.md` 의 형식에 맞춰 **곽동규 개인 기록으로 다시 쓴다.**

- **남길 것:** 곽동규가 실제로 한 작업(이 PR 포함), 실제로 한 검증과 결과, 곽동규의 다음 작업
  (기존 5장 "유사 서비스 조사 / 화면 목록 / 채팅 와이어프레임 / 팀 회의 후 프론트엔드" — 상세는 `docs/tasks/곽동규.md` 링크로 대신하고 요약만)
- **뺄 것:** 팀 전체 구현 상태 표(기존 3장), 팀 전체 남은 작업(6장), 세션 시작·종료 절차(1장·7장)
  → 이미 `CLAUDE.md`, `docs/handoff/README.md`, `docs/tasks/` 에 있으므로 중복하지 않는다.
- 구현 상태를 언급해야 하면 **지금 main 의 코드를 직접 확인**해서 적는다. (예: `frontend/` 에 React 프로토타입이 이미 머지됐을 수 있다. 옛 문서 내용을 그대로 옮기지 않는다)
- 실행하지 않은 검증은 "미실행"으로 적는다.
- 최종 갱신일은 오늘 날짜, 브랜치는 `docs/agent-handoff`.

### 5. 이 지시서 삭제

```bash
git rm docs/tasks/곽동규_PR2_수정.md
```

### 6. 확인

```bash
git diff --stat origin/main...HEAD
```
→ "목표 상태" 표의 3개 파일만 나와야 한다. 다른 파일이 보이면 그 파일을 `git checkout origin/main -- <파일>` 로 되돌린다.

```bash
git diff origin/main -- CLAUDE.md     # 비어 있어야 함
test ! -e NEXT_STEPS.md && echo OK    # NEXT_STEPS.md 가 없어야 함
```

### 7. 커밋하고 같은 브랜치에 push

```bash
git add AGENTS.md docs/handoff/곽동규.md
git commit -m "docs: move handoff to docs/handoff/곽동규.md, keep CLAUDE.md as main"
git push origin docs/agent-handoff
```

- **새 PR을 만들지 않는다.** push하면 PR #2에 자동으로 반영된다.
- **머지하지 않는다.** 머지는 장우석이 확인 후 한다.

### 8. 사용자에게 보고

- 바뀐 파일 목록 (`git diff --stat origin/main...HEAD` 결과)
- 충돌이 있었는지, 어떻게 해결했는지
- "단톡에 'PR #2 수정했어'라고 남겨 달라"는 안내
