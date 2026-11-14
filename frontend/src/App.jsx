import { useState } from "react";
import ScenarioList from "./pages/ScenarioList.jsx";
import Play from "./pages/Play.jsx";
import Report from "./pages/Report.jsx";

// 화면 3개를 상태값 하나로 전환한다. (라우터 라이브러리 없이 단순하게)
//   list   → 시나리오 목록
//   play   → 채팅 플레이 (scenario 필요)
//   report → 종료 리포트 (sessionId 필요)
export default function App() {
  const [screen, setScreen] = useState({ name: "list" });

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen({ name: "list" })}>
          🚒 MIA <span>재난 대응 롤플레잉</span>
        </button>
      </header>

      {screen.name === "list" && (
        <ScenarioList onSelect={(scenario) => setScreen({ name: "play", scenario })} />
      )}
      {screen.name === "play" && (
        <Play
          key={screen.playKey}
          scenario={screen.scenario}
          onFinish={(sessionId) => setScreen({ name: "report", sessionId, scenario: screen.scenario })}
          onExit={() => setScreen({ name: "list" })}
        />
      )}
      {screen.name === "report" && (
        <Report
          sessionId={screen.sessionId}
          onRetry={() => setScreen({ name: "play", scenario: screen.scenario, playKey: Date.now() })}
          onHome={() => setScreen({ name: "list" })}
        />
      )}
    </div>
  );
}
