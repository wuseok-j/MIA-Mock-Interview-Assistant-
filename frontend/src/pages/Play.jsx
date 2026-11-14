import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { categoryEmoji, riskLevel } from "../ui.js";

const MAX_LEN = 300;

export default function Play({ scenario, onFinish, onExit }) {
  const [turn, setTurn] = useState(null);        // 마지막으로 받은 Turn (상태값: 단계·위험도·status)
  const [messages, setMessages] = useState([]);  // 지금까지의 채팅 전체
  const [pending, setPending] = useState("");    // 서버 응답을 기다리는 내 말
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const started = useRef(false);
  const chatBox = useRef(null);

  // 화면이 열리면 플레이 시작 (개발 모드에서 두 번 실행되는 것을 막기 위해 ref 사용)
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    start();
  }, []);

  // 새 메시지가 오면 채팅창만 맨 아래로 스크롤
  useEffect(() => {
    const box = chatBox.current;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
  }, [messages, pending, error]);

  async function start() {
    setError("");
    try {
      const t = await api.startSession(scenario.id);
      setTurn(t);
      setMessages(t.messages);
    } catch (e) {
      started.current = false;
      setError(e.message);
    }
  }

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || pending || turn?.status !== "playing") return;
    setPending(text);
    setInput("");
    setError("");
    try {
      const t = await api.sendMessage(turn.session_id, text);
      setTurn(t);
      setMessages((prev) => [...prev, ...t.messages]); // 서버가 내 말도 같이 돌려준다
    } catch (err) {
      setInput(text); // 실패하면 쓴 문장을 되돌려 놓는다
      setError(err.message);
    } finally {
      setPending("");
    }
  }

  const ended = turn && turn.status !== "playing";

  return (
    <main className="play">
      {/* 상단: 시나리오 제목, 단계 진행, 위험도 */}
      <div className="play-status">
        <div className="play-title">
          <button className="ghost" onClick={onExit}>← 목록</button>
          <strong>{scenario.title}</strong>
        </div>
        {turn && (
          <div className="gauges">
            <StageDots current={turn.stage} total={turn.total_stages} status={turn.status} />
            <RiskGauge risk={turn.risk} max={turn.max_risk} />
          </div>
        )}
      </div>

      {/* 장면 패널: 장면 이미지(turn.image)가 준비되기 전까지는 이모지 + 단계 이름. 위험도가 오르면 색이 붉어진다 */}
      {turn && (
        <div className={`scene risk-${riskLevel(turn.risk, turn.max_risk)}`}>
          <div className="scene-emoji">{categoryEmoji(scenario.category)}</div>
          <div>
            <div className="scene-stage">STAGE {turn.stage} / {turn.total_stages}</div>
            <div className="scene-title">{turn.stage_title}</div>
          </div>
        </div>
      )}

      {/* 채팅 */}
      <div className="chat" ref={chatBox}>
        {messages.map((m, i) => <Bubble key={i} m={m} />)}
        {pending && <Bubble m={{ role: "user", name: "나", text: pending }} dim />}
        {pending && <div className="typing">상대가 반응하는 중…</div>}
        {error && (
          <div className="error-box">
            {error} {!turn && <button onClick={start}>다시 시도</button>}
          </div>
        )}
      </div>

      {/* 입력창 또는 종료 배너 */}
      {ended ? (
        <div className={`end-banner ${turn.status}`}>
          <span>{turn.status === "cleared" ? "🎉 대피 성공!" : "⚠️ 대피 실패"}</span>
          <button className="primary" onClick={() => onFinish(turn.session_id)}>리포트 보기</button>
        </div>
      ) : (
        <form className="composer" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_LEN))}
            placeholder={turn ? "어떻게 행동할지 말해 보세요" : "준비 중…"}
            disabled={!turn || !!pending}
            autoFocus
          />
          <span className="count">{input.length}/{MAX_LEN}</span>
          <button className="primary" disabled={!turn || !!pending || !input.trim()}>보내기</button>
        </form>
      )}
    </main>
  );
}

function Bubble({ m, dim }) {
  if (m.role === "narrator") return <div className="narration">📍 {m.text}</div>;
  if (m.role === "system") return <div className="system-note">{m.text}</div>;
  const mine = m.role === "user";
  return (
    <div className={`bubble-row ${mine ? "mine" : ""} ${dim ? "dim" : ""}`}>
      {!mine && <div className="avatar">{m.name.slice(0, 1)}</div>}
      <div>
        {!mine && <div className="speaker">{m.name}</div>}
        <div className="bubble">{m.text}</div>
      </div>
    </div>
  );
}

function StageDots({ current, total, status }) {
  return (
    <div className="stage-dots" title={`${current}/${total}단계`}>
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1;
        const done = n < current || status === "cleared";
        return <span key={n} className={done ? "done" : n === current ? "now" : ""} />;
      })}
      <small>{current}/{total}</small>
    </div>
  );
}

function RiskGauge({ risk, max }) {
  const pct = Math.min(100, Math.round((risk / max) * 100));
  return (
    <div className="risk" title="위험도가 끝까지 차면 대피 실패">
      <small>위험도</small>
      <div className="risk-bar">
        <div className={`risk-fill risk-${riskLevel(risk, max)}`} style={{ width: `${pct}%` }} />
      </div>
      <small>{Math.min(risk, max)}/{max}</small>
    </div>
  );
}
