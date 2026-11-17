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
          <div className="eyebrow">AFTER ACTION REVIEW · 판단 복기</div>
          <h1>{report.scenario_title} — {cleared ? "건물 밖 도착" : "대피 중단"}</h1>
          <p className="score">
            <strong>{report.passed}</strong> / {report.total} 단계 행동 기준 충족
            <span className="dot">·</span> 최종 위험도 {Math.min(report.risk, report.max_risk)}/{report.max_risk}
          </p>
          {report.summary && <p className="summary">{report.summary}</p>}
        </div>
      </section>

      <section className="review-focus"><h2 className="section-title">다음 연습에서 집중할 판단</h2>
        <p>{report.review_points?.length ? report.review_points.join(" · ") : "모든 단계의 행동 기준을 확인했습니다. 다른 표현과 판단 순서로 다시 연습해 보세요."}</p>
      </section>
      {!!report.timeline?.length && <>
        <h2 className="section-title">내 선택이 만든 경로</h2>
        <ol className="decision-timeline">{report.timeline.map((event, i) => <li key={i} className={event.verdict}>
          <small>{event.stage}단계 · {event.title}</small><blockquote>{event.action}</blockquote>
          <p>{event.outcome} <span>위험도 {event.risk_before} → {event.risk_after}</span></p>
        </li>)}</ol>
      </>}
      <h2 className="section-title">발언과 기준으로 확인하기</h2>
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
            {!!c.evidence?.length && <ul className="evidence-list">{c.evidence.map(item => <li key={item.id}>
              <strong>{item.met ? "확인" : "미확인"} · {item.label}</strong>
              {item.quote && <blockquote>{item.quote}</blockquote>}
              {item.sources.map(source => <a key={source.url} href={source.url} target="_blank" rel="noreferrer">행동 기준 근거 ↗</a>)}
            </li>)}</ul>}
            <div className="action-evidence">
              <b>내 판단 기록 · {c.attempts || 0}회</b>
              {c.user_actions?.length ? c.user_actions.map((text, i) => <blockquote key={i}>{text}</blockquote>) : <p>평가할 발언이 없습니다.</p>}
            </div>
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
