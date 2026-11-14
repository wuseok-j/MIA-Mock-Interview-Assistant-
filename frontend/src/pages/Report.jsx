import { useEffect, useState } from "react";
import { api } from "../api.js";

const RESULT = {
  correct: { icon: "✅", label: "통과" },
  failed: { icon: "❌", label: "보완 필요" },
  not_reached: { icon: "⏸️", label: "도달 못 함" },
};

export default function Report({ sessionId, onRetry, onHome }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  const load = () => {
    setError("");
    api.getReport(sessionId).then(setReport).catch((e) => setError(e.message));
  };
  useEffect(load, [sessionId]);

  if (error) {
    return (
      <main className="page">
        <div className="error-box">{error} <button onClick={load}>다시 시도</button></div>
      </main>
    );
  }
  if (!report) return <main className="page"><p className="muted">리포트를 만드는 중…</p></main>;

  const cleared = report.status === "cleared";
  return (
    <main className="page report">
      <section className={`report-head ${report.status}`}>
        <div className="report-emoji">{cleared ? "🎉" : "🧯"}</div>
        <div>
          <h1>{report.scenario_title} — {cleared ? "대피 성공" : "대피 실패"}</h1>
          <p className="score">
            <strong>{report.passed}</strong> / {report.total} 단계 올바르게 판단
            <span className="dot">·</span> 최종 위험도 {Math.min(report.risk, report.max_risk)}/{report.max_risk}
          </p>
          {report.summary && <p className="summary">{report.summary}</p>}
        </div>
      </section>

      <h2 className="section-title">단계별 피드백</h2>
      <ol className="checks">
        {report.checks.map((c) => (
          <li key={c.id} className={`check ${c.result}`}>
            <div className="check-head">
              <span className="check-icon">{RESULT[c.result].icon}</span>
              <div>
                <div className="check-stage">{c.stage}단계 · {c.stage_title}</div>
                <div className="check-criterion">{c.criterion}</div>
              </div>
              <span className="check-label">{RESULT[c.result].label}</span>
            </div>
            {c.comment && <p className="check-comment">{c.comment}</p>}
            <p className="check-answer"><b>올바른 행동</b> {c.correct_action}</p>
          </li>
        ))}
      </ol>

      {report.sources.length > 0 && (
        <p className="sources">
          행동 기준 출처:{" "}
          {report.sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ", "}
              <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a>
            </span>
          ))}
        </p>
      )}

      <div className="actions">
        <button className="primary" onClick={onRetry}>다시 도전</button>
        <button onClick={onHome}>다른 시나리오</button>
      </div>
    </main>
  );
}
