// 서버 호출은 전부 이 파일에서. 형식은 docs/api-spec.md 참고.

async function request(path, options = {}, token) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000); // 30초 넘으면 실패 처리
  try {
    const res = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(token ? { "X-Admin-Token": token } : {}) },
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      // 운영자 저장 실패(422)는 detail 이 {message, errors, warnings} 객체로 온다
      const d = body.detail;
      const err = new Error(typeof d === "string" ? d : d?.message || "요청을 처리하지 못했어요.");
      err.status = res.status;
      if (d && typeof d === "object") Object.assign(err, { errors: d.errors || [], warnings: d.warnings || [] });
      throw err;
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
  // adminToken 을 주면 작성 중(draft) 시나리오도 시작된다 (운영자 미리 플레이)
  startSession: (scenarioId, adminToken) =>
    request("/sessions", { method: "POST", body: JSON.stringify({ scenario_id: scenarioId }) }, adminToken),
  sendMessage: (sessionId, text) =>
    request(`/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  getReport: (sessionId) => request(`/sessions/${sessionId}/report`),
};

// ---------- 운영자 CMS (/admin) — 모든 요청에 운영자 토큰이 필요하다 ----------
const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const adminApi = {
  list: (t) => request("/admin/scenarios", {}, t),
  get: (t, id) => request(`/admin/scenarios/${id}`, {}, t),
  create: (t, data) => request("/admin/scenarios", json("POST", data), t),
  duplicate: (t, fromId, data) => request(`/admin/scenarios/${fromId}/duplicate`, json("POST", data), t),
  save: (t, sc) => request(`/admin/scenarios/${sc.id}`, json("PUT", sc), t),
  setStatus: (t, id, status) => request(`/admin/scenarios/${id}/status`, json("POST", { status }), t),
  validate: (t, sc) => request("/admin/validate", json("POST", sc), t),
};

// 운영자 토큰은 이 브라우저 탭에만 잠깐 기억한다 (창을 닫으면 사라짐)
export const adminSession = {
  load() { try { return sessionStorage.getItem("mia-admin-token") || ""; } catch { return ""; } },
  save(t) { try { sessionStorage.setItem("mia-admin-token", t); } catch { /* 저장 불가 환경은 무시 */ } },
  clear() { try { sessionStorage.removeItem("mia-admin-token"); } catch { /* 무시 */ } },
};
