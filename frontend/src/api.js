// 서버 호출은 전부 이 파일에서. 형식은 docs/api-spec.md 참고.

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000); // 30초 넘으면 실패 처리
  try {
    const res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = typeof body.detail === "string" ? body.detail : "요청을 처리하지 못했어요.";
      throw new Error(detail);
    }
    return res.json();
  } catch (e) {
    if (e.name === "AbortError") throw new Error("응답이 너무 늦어요. 잠시 후 다시 시도해 주세요.");
    if (e instanceof TypeError) throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  listScenarios: () => request("/scenarios"),
  startSession: (scenarioId) =>
    request("/sessions", { method: "POST", body: JSON.stringify({ scenario_id: scenarioId }) }),
  sendMessage: (sessionId, text) =>
    request(`/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  getReport: (sessionId) => request(`/sessions/${sessionId}/report`),
};
