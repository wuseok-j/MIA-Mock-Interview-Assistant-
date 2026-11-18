import { useEffect, useState } from "react";
import { activePlay, api } from "../api.js";
import { categoryEmoji } from "../ui.js";

export default function ScenarioList({ onSelect, onResume }) {
  const [scenarios, setScenarios] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState(activePlay.load());   // 진행 중이던 플레이 (이어하기)

  const load = () => {
    setError("");
    api.listScenarios().then(setScenarios).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  return (
    <main className="page">
      <section className="hero">
        <div className="eyebrow">MIA · DECISION LAB</div>
        <h1>당신의 한마디가,<br />다음 상황을 바꿉니다.</h1>
        <p>동료를 설득하고, 경로를 판단하고, 내 선택의 근거를 복기하는 재난 대응 연습.</p>
        <div className="feature-grid">
          <div><b>01 · 선택이 남는 상황</b><span>앞선 판단이 다음 장면에 반영됩니다.</span></div>
          <div><b>02 · 행동 단위 확인</b><span>단어 하나 대신 필요한 행동을 모읍니다.</span></div>
          <div><b>03 · 근거로 돌아보기</b><span>내 발언과 행동 기준을 나란히 봅니다.</span></div>
        </div>
      </section>

      {active && (
        <div className="resume-banner">
          <div>
            <b>진행 중인 플레이가 있어요</b>
            <span>{active.scenario.title} · 서버에 저장된 곳부터 이어서 할 수 있습니다.</span>
          </div>
          <div className="resume-actions">
            <button className="primary" onClick={() => onResume(active)}>이어하기</button>
            <button onClick={() => { activePlay.clear(); setActive(null); }}>닫기</button>
          </div>
        </div>
      )}

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
              <button className="primary" onClick={() => onSelect(sc)}>임무 확인하기 →</button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
