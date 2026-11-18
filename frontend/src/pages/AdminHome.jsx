import { useEffect, useState } from "react";
import { adminApi, adminSession } from "../api.js";

// 운영자 첫 화면: 토큰 입력 → 시나리오 목록·이용 현황 → 새로 만들기·복제·공개
export default function AdminHome({ onEdit, onPreview }) {
  const [token, setToken] = useState(adminSession.load());
  const [input, setInput] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ mode: "new", from: "", id: "", title: "", category: "화재" });
  const [busy, setBusy] = useState(false);

  const load = (t = token) => {
    if (!t) return;
    setError("");
    adminApi.list(t).then(setRows).catch((e) => {
      if (e.status === 401) { adminSession.clear(); setToken(""); }
      setError(e.message);
    });
  };
  useEffect(() => { load(); }, [token]);

  function login(e) {
    e.preventDefault();
    const t = input.trim();
    adminApi.list(t).then((r) => { adminSession.save(t); setToken(t); setRows(r); setError(""); })
      .catch((err) => setError(err.message));
  }

  async function create(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const data = { id: form.id.trim(), title: form.title.trim(), category: form.category.trim() || "기타" };
      const r = form.mode === "copy" && form.from
        ? await adminApi.duplicate(token, form.from, data)
        : await adminApi.create(token, data);
      onEdit(r.scenario.id);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function toggle(row) {
    setError("");
    try {
      await adminApi.setStatus(token, row.id, row.status === "published" ? "draft" : "published");
      load();
    } catch (err) {
      setError(err.errors?.length ? `${err.message} (${err.errors.length}개 오류 — 편집 화면에서 확인)` : err.message);
    }
  }

  if (!token) {
    return (
      <main className="page admin">
        <section className="admin-login">
          <div className="eyebrow">OPERATOR · 운영자</div>
          <h1>시나리오 관리</h1>
          <p className="muted">교사·안전 담당자가 재난 시나리오를 만들고 공개하는 화면입니다. 서버의 <code>.env</code> 에 설정한 운영자 토큰을 입력하세요.</p>
          <form onSubmit={login} className="admin-login-form">
            <label htmlFor="admin-token">운영자 토큰</label>
            <input id="admin-token" type="password" value={input} onChange={(e) => setInput(e.target.value)} autoComplete="off" />
            <button className="primary" disabled={!input.trim()}>들어가기</button>
          </form>
          {error && <div className="error-box">{error}</div>}
        </section>
      </main>
    );
  }

  return (
    <main className="page admin">
      <section className="admin-head">
        <div>
          <div className="eyebrow">OPERATOR · 운영자</div>
          <h1>시나리오 관리</h1>
        </div>
        <button className="ghost" onClick={() => { adminSession.clear(); setToken(""); setRows(null); }}>나가기</button>
      </section>
      {error && <div className="error-box">{error}</div>}

      <table className="admin-table">
        <thead>
          <tr><th>시나리오</th><th>상태</th><th>검사</th><th>이용 현황</th><th></th></tr>
        </thead>
        <tbody>
          {!rows && <tr><td colSpan={5} className="muted">불러오는 중…</td></tr>}
          {rows?.map((r) => (
            <tr key={r.id}>
              <td>
                <b>{r.title}</b>
                <div className="muted small">{r.category} · {r.total_stages}단계 · <code>{r.id}</code>{r.version ? ` · v${r.version}` : ""}</div>
              </td>
              <td><span className={`chip ${r.status}`}>{r.status === "published" ? "공개" : "작성 중"}</span></td>
              <td>
                {r.errors ? <span className="chip bad">오류 {r.errors}</span> : <span className="chip good">통과</span>}
                {!!r.warnings && <span className="chip warn">확인 {r.warnings}</span>}
              </td>
              <td className="small">
                플레이 {r.stats.plays}회 · 완료 {r.stats.finished}회
                {r.stats.avg_passed !== null && <div className="muted">평균 {r.stats.avg_passed}/{r.total_stages}단계 통과</div>}
                {!!Object.keys(r.stats.stage_fail).length && (
                  <div className="muted">많이 놓친 단계: {Object.entries(r.stats.stage_fail).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([s, n]) => `${s}단계(${n})`).join(", ")}</div>
                )}
                {!!r.stats.ai?.calls && (
                  <div className="muted">
                    AI {r.stats.ai.calls}회 · 평균 {(r.stats.ai.avg_latency_ms / 1000).toFixed(1)}초
                    · 토큰 {Math.round((r.stats.ai.input_tokens + r.stats.ai.output_tokens) / Math.max(1, r.stats.plays)).toLocaleString()}/판
                    {r.stats.ai.cost_per_play_krw !== null ? ` · 약 ${r.stats.ai.cost_per_play_krw}원/판` : " · 비용: .env 가격 미설정"}
                    {!!r.stats.ai.fallbacks && ` · 실패 ${r.stats.ai.fallbacks}회`}
                  </div>
                )}
              </td>
              <td className="row-actions">
                <button onClick={() => onEdit(r.id)}>편집</button>
                <button onClick={() => onPreview(r)}>미리 플레이</button>
                <button onClick={() => toggle(r)}>{r.status === "published" ? "비공개로" : "공개하기"}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">이용 현황은 DB(<code>backend/mia.db</code>)에 저장된 전체 기록입니다. AI 수치는 실제 AI 호출만 셉니다 (가짜 AI 제외).</p>

      <section className="admin-card">
        <h2>새 시나리오</h2>
        <form className="admin-new" onSubmit={create}>
          <div className="seg" role="group" aria-label="만드는 방식">
            <button type="button" aria-pressed={form.mode === "new"} onClick={() => setForm({ ...form, mode: "new" })}>빈 뼈대로</button>
            <button type="button" aria-pressed={form.mode === "copy"} onClick={() => setForm({ ...form, mode: "copy", from: form.from || rows?.[0]?.id || "" })}>기존 시나리오 복제</button>
          </div>
          {form.mode === "copy" && (
            <label>복제할 시나리오
              <select value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })}>
                {rows?.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
              </select>
            </label>
          )}
          <label>id (영문 소문자·숫자·밑줄, 파일 이름이 됩니다)
            <input value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} placeholder="earthquake_school" required pattern="[a-z][a-z0-9_]{2,39}" />
          </label>
          <label>제목
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="학교 지진 대응" required maxLength={80} />
          </label>
          <label>카테고리
            <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="지진" maxLength={20} />
          </label>
          <button className="primary" disabled={busy}>{busy ? "만드는 중…" : "만들고 편집하기"}</button>
        </form>
        <p className="muted small">새 시나리오는 '작성 중' 상태로 만들어져 이용자에게 보이지 않습니다. 검사 오류가 0개가 되면 공개할 수 있습니다.</p>
      </section>
    </main>
  );
}
