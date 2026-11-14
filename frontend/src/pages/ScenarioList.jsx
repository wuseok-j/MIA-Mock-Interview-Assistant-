import { useEffect, useState } from "react";
import { api } from "../api.js";
import { categoryEmoji } from "../ui.js";

export default function ScenarioList({ onSelect }) {
  const [scenarios, setScenarios] = useState(null);
  const [error, setError] = useState("");

  const load = () => {
    setError("");
    api.listScenarios().then(setScenarios).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  return (
    <main className="page">
      <section className="hero">
        <h1>실제 상황처럼, 직접 판단해 보세요</h1>
        <p>재난 상황 속 인물과 대화하며 행동을 결정하고, 끝나면 단계별 피드백을 받습니다.</p>
      </section>

      {error && (
        <div className="error-box">
          {error} <button onClick={load}>다시 시도</button>
        </div>
      )}
      {!scenarios && !error && <p className="muted">시나리오를 불러오는 중…</p>}

      <div className="card-grid">
        {scenarios?.map((sc) => (
          <article key={sc.id} className="scenario-card">
            <div className="thumb">{categoryEmoji(sc.category)}</div>
            <div className="card-body">
              <span className="tag">{sc.category}</span>
              <h2>{sc.title}</h2>
              <p>{sc.summary}</p>
              <ul className="meta">
                <li>{sc.total_stages}단계</li>
                {sc.estimated_minutes && <li>약 {sc.estimated_minutes}분</li>}
                <li>등장인물 {sc.characters.map((c) => c.name).join(", ")}</li>
              </ul>
              <button className="primary" onClick={() => onSelect(sc)}>시작하기</button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
