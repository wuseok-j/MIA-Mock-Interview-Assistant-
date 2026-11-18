import { useState } from "react";
import ScenarioList from "./pages/ScenarioList.jsx";
import Play from "./pages/Play.jsx";
import Report from "./pages/Report.jsx";
import Briefing from "./pages/Briefing.jsx";
import AdminHome from "./pages/AdminHome.jsx";
import AdminEditor from "./pages/AdminEditor.jsx";
import { adminSession } from "./api.js";

// 화면을 상태값 하나로 전환한다. (라우터 라이브러리 없이 단순하게)
// 이용자:  list → briefing → play → report
// 운영자:  admin(목록) → adminEdit(편집) → preview(미리 플레이) → report
export default function App() {
  const [screen, setScreen] = useState({ name: "list" });
  const isAdmin = screen.name.startsWith("admin") || screen.preview;

  // 운영자 화면에서 미리 플레이할 때 넘길 시나리오 정보 (Play 가 쓰는 필드만)
  const previewOf = (sc) => ({ id: sc.id, title: sc.title, category: sc.category, briefing: sc.briefing || {} });

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen({ name: "list" })}>
          🚒 MIA <span>재난 대응 롤플레잉</span>
        </button>
        <button className={`topbar-link ${isAdmin ? "active" : ""}`} onClick={() => setScreen({ name: "admin" })}>운영자</button>
      </header>

      {screen.name === "list" && (
        <ScenarioList onSelect={(scenario) => setScreen({ name: "briefing", scenario })} />
      )}
      {screen.name === "briefing" && (
        <Briefing scenario={screen.scenario}
          onStart={() => setScreen({ name: "play", scenario: screen.scenario })}
          onBack={() => setScreen({ name: "list" })} />
      )}
      {screen.name === "play" && (
        <Play
          key={screen.playKey}
          scenario={screen.scenario}
          adminToken={screen.preview ? adminSession.load() : undefined}
          onFinish={(sessionId) => setScreen({ name: "report", sessionId, scenario: screen.scenario, preview: screen.preview })}
          onExit={() => setScreen(screen.preview ? { name: "adminEdit", id: screen.scenario.id } : { name: "list" })}
        />
      )}
      {screen.name === "report" && (
        <Report
          sessionId={screen.sessionId}
          onRetry={() => setScreen({ name: "play", scenario: screen.scenario, playKey: Date.now(), preview: screen.preview })}
          onHome={() => setScreen(screen.preview ? { name: "adminEdit", id: screen.scenario.id } : { name: "list" })}
        />
      )}
      {screen.name === "admin" && (
        <AdminHome
          onEdit={(id) => setScreen({ name: "adminEdit", id })}
          onPreview={(row) => setScreen({ name: "play", scenario: previewOf(row), preview: true, playKey: Date.now() })}
        />
      )}
      {screen.name === "adminEdit" && (
        <AdminEditor
          token={adminSession.load()}
          scenarioId={screen.id}
          onBack={() => setScreen({ name: "admin" })}
          onPreview={(sc) => setScreen({ name: "play", scenario: previewOf(sc), preview: true, playKey: Date.now() })}
        />
      )}
    </div>
  );
}
