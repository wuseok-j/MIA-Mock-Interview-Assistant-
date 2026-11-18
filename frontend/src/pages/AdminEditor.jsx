import { useEffect, useRef, useState } from "react";
import { adminApi } from "../api.js";

// 시나리오 편집기. 시나리오 JSON 의 각 부분을 탭으로 나눠 폼으로 고친다.
// 저장하면 서버가 검사(scenario_check.py)하고, 오류가 있으면 저장하지 않고 목록으로 보여 준다.
const TABS = [
  ["basic", "기본 정보"],
  ["world", "배경·캐릭터"],
  ["stages", "단계"],
  ["eval", "평가·출처"],
  ["json", "JSON (고급)"],
];

const clone = (x) => JSON.parse(JSON.stringify(x));
const lines = (arr) => (arr || []).join("\n");
const toLines = (text, { noSpace = false } = {}) =>
  text.split("\n").map((s) => (noSpace ? s.replace(/\s+/g, "") : s.trim())).filter(Boolean);

function newStage(n, charId) {
  return {
    stage: n, title: `${n}단계`, situation: "", character_id: charId, opening_line: "", correct_action: "",
    keywords: [], wrong_keywords: [], next_if_correct: null,
    if_wrong: { narration: "", risk_delta: 2 },
    reactions: { correct: "", wrong: "", unclear: "" },
    partial_reply: "", facts: [], image: "", rubric: [], danger_patterns: [],
  };
}

// 단계를 추가·삭제·이동한 뒤 번호와 '다음 단계' 연결을 자동으로 맞춘다
function renumber(stages) {
  return stages.map((st, i) => ({ ...st, stage: i + 1, next_if_correct: i + 1 < stages.length ? i + 2 : null }));
}

export default function AdminEditor({ token, scenarioId, onBack, onPreview }) {
  const [sc, setSc] = useState(null);
  const [saved, setSaved] = useState(null);       // 마지막으로 저장된 내용 (변경 여부 비교용)
  const [check, setCheck] = useState({ errors: [], warnings: [] });
  const [tab, setTab] = useState("basic");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [leaveWarned, setLeaveWarned] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    adminApi.get(token, scenarioId).then((r) => {
      setSc(r.scenario); setSaved(JSON.stringify(r.scenario)); setCheck({ errors: r.errors, warnings: r.warnings });
    }).catch((e) => setError(e.message));
  }, [token, scenarioId]);

  // 고칠 때마다 0.6초 뒤 저장 없이 검사만 한다
  useEffect(() => {
    if (!sc) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      adminApi.validate(token, sc).then(setCheck).catch(() => {});
    }, 600);
    return () => clearTimeout(timer.current);
  }, [sc, token]);

  if (error && !sc) return <main className="page admin"><div className="error-box">{error}</div><button onClick={onBack}>← 목록</button></main>;
  if (!sc) return <main className="page admin"><p className="muted">불러오는 중…</p></main>;

  const dirty = JSON.stringify(sc) !== saved;
  const update = (fn) => setSc((prev) => { const next = clone(prev); fn(next); return next; });

  async function save() {
    setBusy(true); setMsg(""); setError("");
    try {
      const r = await adminApi.save(token, sc);
      setSc(r.scenario); setSaved(JSON.stringify(r.scenario));
      setCheck({ errors: r.errors, warnings: r.warnings });
      setMsg("저장했습니다.");
    } catch (e) {
      setError(e.message);
      if (e.errors) setCheck({ errors: e.errors, warnings: e.warnings || [] });
    } finally { setBusy(false); }
  }

  async function toggleStatus() {
    setError(""); setMsg("");
    if (dirty) { setError("먼저 저장해 주세요."); return; }
    try {
      const next = sc.status === "published" ? "draft" : "published";
      await adminApi.setStatus(token, sc.id, next);
      const r = await adminApi.get(token, sc.id);
      setSc(r.scenario); setSaved(JSON.stringify(r.scenario));
      setMsg(next === "published" ? "공개했습니다. 이용자 목록에 보입니다." : "비공개로 바꿨습니다.");
    } catch (e) { setError(e.message); }
  }

  return (
    <main className="page admin editor">
      <section className="admin-head">
        <div>
          <button className="ghost" onClick={() => {
            // 저장 안 한 내용이 있으면 한 번 경고하고, 다시 누르면 나간다
            if (dirty && !leaveWarned) { setLeaveWarned(true); setError("저장하지 않은 내용이 있습니다. 그래도 나가려면 '← 목록'을 한 번 더 누르세요."); return; }
            onBack();
          }}>← 목록</button>
          <h1>{sc.title || sc.id}</h1>
          <div className="muted small"><code>{sc.id}</code> · <span className={`chip ${sc.status || "published"}`}>{sc.status === "draft" ? "작성 중" : "공개"}</span>
            {dirty && <span className="chip warn">저장 안 됨</span>}</div>
        </div>
        <div className="editor-actions">
          <button onClick={() => onPreview(sc)} disabled={dirty} title={dirty ? "저장 후 미리 플레이할 수 있어요" : ""}>미리 플레이</button>
          <button onClick={toggleStatus}>{sc.status === "draft" ? "공개하기" : "비공개로"}</button>
          <button className="primary" onClick={save} disabled={busy || !dirty}>{busy ? "저장 중…" : "저장"}</button>
        </div>
      </section>

      {msg && <div className="ok-box">{msg}</div>}
      {error && <div className="error-box">{error}</div>}
      <CheckPanel check={check} />

      <div className="tabs" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === "basic" && <BasicTab sc={sc} update={update} />}
      {tab === "world" && <WorldTab sc={sc} update={update} />}
      {tab === "stages" && <StagesTab sc={sc} update={update} />}
      {tab === "eval" && <EvalTab sc={sc} update={update} />}
      {tab === "json" && <JsonTab sc={sc} setSc={setSc} />}
    </main>
  );
}

function CheckPanel({ check }) {
  if (!check.errors.length && !check.warnings.length) {
    return <div className="check-panel good">검사 통과 — 저장·공개할 수 있습니다.</div>;
  }
  return (
    <details className={`check-panel ${check.errors.length ? "bad" : "warn"}`} open={!!check.errors.length}>
      <summary>
        {check.errors.length ? `오류 ${check.errors.length}개 (고쳐야 저장·공개 가능)` : "오류 없음"}
        {!!check.warnings.length && ` · 확인 필요 ${check.warnings.length}개`}
      </summary>
      <ul>
        {check.errors.map((e, i) => <li key={`e${i}`} className="bad">{e}</li>)}
        {check.warnings.map((w, i) => <li key={`w${i}`}>{w}</li>)}
      </ul>
    </details>
  );
}

// ---------- 작은 입력 부품 ----------
function Field({ label, hint, value, onChange, multiline, type = "text", ...rest }) {
  return (
    <label className="field">
      <span>{label}{hint && <small>{hint}</small>}</span>
      {multiline
        ? <textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)} rows={multiline === true ? 3 : multiline} {...rest} />
        : <input type={type} value={value ?? ""} onChange={(e) => onChange(type === "number" ? Number(e.target.value) : e.target.value)} {...rest} />}
    </label>
  );
}

// 한 줄에 하나씩 쓰는 목록. 입력 중에는 그대로 두고, 칸을 벗어날 때 정리한다.
function LinesField({ label, hint, value, onChange, noSpace, rows = 3 }) {
  const [text, setText] = useState(lines(value));
  useEffect(() => { setText(lines(value)); }, [JSON.stringify(value)]);
  return (
    <label className="field">
      <span>{label}<small>{hint ? `${hint} · ` : ""}한 줄에 하나</small></span>
      <textarea value={text} rows={rows} onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(toLines(text, { noSpace }))} />
    </label>
  );
}

// ---------- 탭: 기본 정보 ----------
function BasicTab({ sc, update }) {
  const b = sc.briefing || {};
  return (
    <section className="admin-card form-grid">
      <Field label="제목" value={sc.title} onChange={(v) => update((s) => { s.title = v; })} maxLength={80} />
      <Field label="카테고리" hint="예: 화재, 지진" value={sc.category} onChange={(v) => update((s) => { s.category = v; })} maxLength={20} />
      <Field label="한 줄 소개" value={sc.summary} onChange={(v) => update((s) => { s.summary = v; })} multiline={2} className="wide" />
      <Field label="예상 시간(분)" type="number" min={1} max={60} value={sc.estimated_minutes} onChange={(v) => update((s) => { s.estimated_minutes = v; })} />
      <Field label="위험도 한도" hint="이 값에 닿으면 실패" type="number" min={1} max={20} value={sc.max_risk} onChange={(v) => update((s) => { s.max_risk = v; })} />
      <Field label="버전" value={sc.version} onChange={(v) => update((s) => { s.version = v; })} />
      <h3 className="wide">시작 전 브리핑 (이용자에게 보임)</h3>
      <Field label="이용자의 역할" value={b.role} onChange={(v) => update((s) => { s.briefing = { ...(s.briefing || {}), role: v }; })} />
      <Field label="임무" value={b.mission} onChange={(v) => update((s) => { s.briefing = { ...(s.briefing || {}), mission: v }; })} multiline={2} className="wide" />
      <LinesField label="연습할 역량" value={b.focus} onChange={(v) => update((s) => { s.briefing = { ...(s.briefing || {}), focus: v }; })} />
    </section>
  );
}

// ---------- 탭: 배경·캐릭터 ----------
function WorldTab({ sc, update }) {
  const role = sc.role_doc || {};
  const setRole = (k, v) => update((s) => { s.role_doc = { ...(s.role_doc || {}), [k]: v }; });
  return (
    <>
      <section className="admin-card form-grid">
        <h3 className="wide">배경 (롤 문서 — AI에게만 전달)</h3>
        <Field label="장소" value={role.place} onChange={(v) => setRole("place", v)} className="wide" />
        <Field label="전체 상황" value={role.situation} onChange={(v) => setRole("situation", v)} multiline className="wide" />
        <LinesField label="캐릭터가 지킬 규칙" value={role.rules} onChange={(v) => setRole("rules", v)} rows={4} />
        <LinesField label="상황 정보" hint="이용자 질문에 AI가 일관되게 답하는 근거. 위치·인원·사정 등 (대피 요령은 쓰지 않기)" value={role.world_facts} onChange={(v) => setRole("world_facts", v)} rows={5} />
      </section>
      <section className="admin-card">
        <div className="card-head"><h3>캐릭터</h3>
          <button onClick={() => update((s) => { s.characters.push({ id: `char${s.characters.length + 1}`, name: "", role: "", personality: "", speech_style: "", image: "" }); })}>+ 캐릭터 추가</button>
        </div>
        {sc.characters.map((c, i) => (
          <div className="sub-card form-grid" key={i}>
            <Field label="id" hint="영문 소문자" value={c.id} onChange={(v) => update((s) => { s.characters[i].id = v; })} />
            <Field label="이름" value={c.name} onChange={(v) => update((s) => { s.characters[i].name = v; })} />
            <Field label="역할" value={c.role} onChange={(v) => update((s) => { s.characters[i].role = v; })} className="wide" />
            <Field label="성격" value={c.personality} onChange={(v) => update((s) => { s.characters[i].personality = v; })} multiline={2} className="wide" />
            <Field label="말투" value={c.speech_style} onChange={(v) => update((s) => { s.characters[i].speech_style = v; })} className="wide" />
            {sc.characters.length > 1 && <button className="danger-link" onClick={() => update((s) => { s.characters.splice(i, 1); })}>이 캐릭터 삭제</button>}
          </div>
        ))}
      </section>
    </>
  );
}

// ---------- 탭: 단계 ----------
function StagesTab({ sc, update }) {
  const [open, setOpen] = useState(0);
  const sources = sc.sources || [];
  const setStages = (fn) => update((s) => { fn(s.stages); s.stages = renumber(s.stages); });
  return (
    <section className="admin-card">
      <div className="card-head"><h3>단계 ({sc.stages.length}개)</h3>
        <button onClick={() => { setStages((st) => st.push(newStage(st.length + 1, sc.characters[0]?.id || ""))); setOpen(sc.stages.length); }}>+ 단계 추가</button>
      </div>
      <p className="muted small">번호와 '다음 단계' 연결은 자동으로 맞춰집니다. 상태별 장면 변형(variants)은 JSON 탭에서 고칩니다.</p>
      {sc.stages.map((st, i) => {
        const set = (fn) => update((s) => { fn(s.stages[i]); });
        return (
          <details className="stage-card" key={i} open={open === i} onToggle={(e) => e.currentTarget.open && setOpen(i)}>
            <summary><b>{st.stage}. {st.title || "(제목 없음)"}</b><span className="muted small">행동 기준 {st.rubric?.length || 0}개 · 위험도 +{st.if_wrong?.risk_delta ?? 0}</span></summary>
            <div className="form-grid">
              <Field label="단계 제목" value={st.title} onChange={(v) => set((x) => { x.title = v; })} />
              <label className="field"><span>말하는 캐릭터</span>
                <select value={st.character_id} onChange={(e) => set((x) => { x.character_id = e.target.value; })}>
                  {sc.characters.map((c) => <option key={c.id} value={c.id}>{c.name || c.id}</option>)}
                </select>
              </label>
              <Field label="상황 설명" hint="이용자에게 보이는 내레이션" value={st.situation} onChange={(v) => set((x) => { x.situation = v; })} multiline className="wide" />
              <Field label="캐릭터 첫 대사" hint="일부러 틀린 행동을 유도하면 판단 연습이 됩니다" value={st.opening_line} onChange={(v) => set((x) => { x.opening_line = v; })} multiline={2} className="wide" />
              <Field label="올바른 행동" hint="공공기관 행동요령 근거. 리포트에 정답으로 공개" value={st.correct_action} onChange={(v) => set((x) => { x.correct_action = v; })} multiline={2} className="wide" />
              <LinesField label="이 단계 상황 정보" hint="질문 대응용" value={st.facts} onChange={(v) => set((x) => { x.facts = v; })} />
              <LinesField label="행동 키워드" hint="AI 오판 방지용 — 이 중 하나는 있어야 통과" value={st.keywords} onChange={(v) => set((x) => { x.keywords = v; })} />
              <Field label="틀렸을 때 전개" value={st.if_wrong?.narration} onChange={(v) => set((x) => { x.if_wrong = { ...(x.if_wrong || {}), narration: v }; })} multiline={2} className="wide" />
              <Field label="틀렸을 때 위험도 +" type="number" min={0} max={10} value={st.if_wrong?.risk_delta} onChange={(v) => set((x) => { x.if_wrong = { ...(x.if_wrong || {}), risk_delta: v }; })} />
              <Field label="일부만 했을 때 대사" hint="AI 응답이 없을 때 쓰는 예비 대사" value={st.partial_reply} onChange={(v) => set((x) => { x.partial_reply = v; })} />
              <h4 className="wide">예비 대사 (AI 장애 시 사용)</h4>
              {["correct", "wrong", "unclear"].map((k) => (
                <Field key={k} label={{ correct: "맞았을 때", wrong: "틀렸을 때", unclear: "애매할 때" }[k]}
                  value={st.reactions?.[k]} onChange={(v) => set((x) => { x.reactions = { ...(x.reactions || {}), [k]: v }; })} />
              ))}
            </div>

            <RubricEditor stage={st} sources={sources} set={set} />
            <LinesField label="위험 행동 패턴" hint="여기에 걸리면 AI 판단과 상관없이 '틀림'. 띄어쓰기 없이" noSpace
              value={st.danger_patterns} onChange={(v) => set((x) => { x.danger_patterns = v; })} />

            <div className="stage-tools">
              <button disabled={i === 0} onClick={() => { setStages((s) => s.splice(i - 1, 0, s.splice(i, 1)[0])); setOpen(i - 1); }}>↑ 위로</button>
              <button disabled={i === sc.stages.length - 1} onClick={() => { setStages((s) => s.splice(i + 1, 0, s.splice(i, 1)[0])); setOpen(i + 1); }}>↓ 아래로</button>
              {sc.stages.length > 1 && <button className="danger-link" onClick={() => setStages((s) => s.splice(i, 1))}>이 단계 삭제</button>}
            </div>
          </details>
        );
      })}
    </section>
  );
}

// 행동 기준(rubric): 서버가 '이 행동을 했다'고 인정하는 조건. AI가 속아도 이걸로 진행을 지킨다.
function RubricEditor({ stage, sources, set }) {
  const rubric = stage.rubric || [];
  return (
    <div className="rubric">
      <div className="card-head"><h4>행동 기준 — 모두 확인돼야 통과</h4>
        <button onClick={() => set((x) => { x.rubric = [...(x.rubric || []), { id: `act${rubric.length + 1}`, label: "", patterns: [[]], exclude: [], source_indices: [] }]; })}>+ 행동 추가</button>
      </div>
      <p className="muted small">인정할 표현: 이용자 말(띄어쓰기 제거 후)에 들어 있으면 인정. 한 칸 안의 줄은 '하나만 있어도 됨', 칸이 여러 개면 '모든 칸을 만족'. 정규식 사용 가능 (예: <code>119.{"{0,8}"}(신고|전화)</code>)</p>
      {rubric.map((item, k) => {
        const setItem = (fn) => set((x) => { fn(x.rubric[k]); });
        return (
          <div className="sub-card form-grid" key={k}>
            <Field label="행동 이름" hint="리포트에 표시" value={item.label} onChange={(v) => setItem((r) => { r.label = v; })} />
            <Field label="id" hint="영문 소문자" value={item.id} onChange={(v) => setItem((r) => { r.id = v; })} />
            {(item.patterns || [[]]).map((group, g) => (
              <LinesField key={g} label={`인정할 표현 ${g + 1}`} noSpace value={group}
                onChange={(v) => setItem((r) => { r.patterns[g] = v; })} />
            ))}
            <div className="wide inline-tools">
              <button onClick={() => setItem((r) => { r.patterns = [...(r.patterns || []), []]; })}>+ 조건 칸 추가 (그리고)</button>
              {(item.patterns || []).length > 1 && <button onClick={() => setItem((r) => { r.patterns.pop(); })}>마지막 칸 빼기</button>}
            </div>
            <LinesField label="제외할 표현" hint="이게 있으면 인정 안 함 (예: 부정)" noSpace value={item.exclude}
              onChange={(v) => setItem((r) => { r.exclude = v; })} />
            {!!sources.length && (
              <fieldset className="field wide"><legend>근거 출처</legend>
                {sources.map((src, si) => (
                  <label key={si} className="check-line">
                    <input type="checkbox" checked={(item.source_indices || []).includes(si)}
                      onChange={(e) => setItem((r) => {
                        const set2 = new Set(r.source_indices || []);
                        e.target.checked ? set2.add(si) : set2.delete(si);
                        r.source_indices = [...set2].sort();
                      })} /> {src.name || `출처 ${si + 1}`}
                  </label>
                ))}
              </fieldset>
            )}
            <button className="danger-link" onClick={() => set((x) => { x.rubric.splice(k, 1); })}>이 행동 삭제</button>
          </div>
        );
      })}
    </div>
  );
}

// ---------- 탭: 평가·출처 ----------
function EvalTab({ sc, update }) {
  const evaluation = sc.evaluation || [];
  const sources = sc.sources || [];
  return (
    <>
      <section className="admin-card">
        <div className="card-head"><h3>평가 기준 (리포트에 표시)</h3>
          <button onClick={() => update((s) => { s.evaluation = [...(s.evaluation || []), { id: `c${evaluation.length + 1}`, stage: s.stages.length, criterion: "" }]; })}>+ 기준 추가</button>
        </div>
        {evaluation.map((ev, i) => (
          <div className="sub-card form-grid" key={i}>
            <Field label="id" value={ev.id} onChange={(v) => update((s) => { s.evaluation[i].id = v; })} />
            <label className="field"><span>단계</span>
              <select value={ev.stage} onChange={(e) => update((s) => { s.evaluation[i].stage = Number(e.target.value); })}>
                {sc.stages.map((st) => <option key={st.stage} value={st.stage}>{st.stage}. {st.title}</option>)}
              </select>
            </label>
            <Field label="기준" value={ev.criterion} onChange={(v) => update((s) => { s.evaluation[i].criterion = v; })} className="wide" />
            <button className="danger-link" onClick={() => update((s) => { s.evaluation.splice(i, 1); })}>삭제</button>
          </div>
        ))}
      </section>
      <section className="admin-card">
        <div className="card-head"><h3>출처 (올바른 행동의 근거)</h3>
          <button onClick={() => update((s) => { s.sources = [...(s.sources || []), { name: "", url: "https://", note: "" }]; })}>+ 출처 추가</button>
        </div>
        {sources.map((src, i) => (
          <div className="sub-card form-grid" key={i}>
            <Field label={`출처 ${i + 1} 이름`} value={src.name} onChange={(v) => update((s) => { s.sources[i].name = v; })} className="wide" />
            <Field label="주소" value={src.url} onChange={(v) => update((s) => { s.sources[i].url = v; })} className="wide" />
            <Field label="메모" hint="몇 단계 근거인지 등" value={src.note} onChange={(v) => update((s) => { s.sources[i].note = v; })} className="wide" />
            <button className="danger-link" onClick={() => update((s) => { s.sources.splice(i, 1); })}>삭제 (행동 기준의 출처 번호가 바뀔 수 있음)</button>
          </div>
        ))}
      </section>
    </>
  );
}

// ---------- 탭: JSON ----------
function JsonTab({ sc, setSc }) {
  const [text, setText] = useState(JSON.stringify(sc, null, 2));
  const [err, setErr] = useState("");
  useEffect(() => { setText(JSON.stringify(sc, null, 2)); }, [sc]);
  return (
    <section className="admin-card">
      <p className="muted small">폼에 없는 항목(상태별 장면 변형 등)은 여기서 고칩니다. '적용'을 눌러도 저장은 따로 눌러야 합니다.</p>
      <textarea className="json-edit" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} rows={28} aria-label="시나리오 JSON" />
      {err && <div className="error-box">{err}</div>}
      <button onClick={() => {
        try {
          const next = JSON.parse(text);
          if (next.id !== sc.id) throw new Error("id 는 바꿀 수 없습니다.");
          setSc(next); setErr("");
        } catch (e) { setErr(`적용할 수 없습니다: ${e.message}`); }
      }}>적용</button>
    </section>
  );
}
