/**
 * API client riêng biệt cho module AI Tutor.
 * Không sửa đổi api.js gốc, đảm bảo tính đóng gói độc lập.
 */

let csrfToken = "";

async function fetchCsrfToken() {
  try {
    const res = await fetch("/api/csrf-token", { credentials: "same-origin" });
    if (res.ok) {
      const data = await res.json();
      csrfToken = data.csrf_token || "";
    }
  } catch (err) {
    console.warn("Không thể lấy mã CSRF token tự động:", err);
  }
  return csrfToken;
}

async function tutorFetch(endpoint, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method)) {
    if (!csrfToken) {
      await fetchCsrfToken();
    }
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`/api/tutor${endpoint}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.error || `Yêu cầu thất bại (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const tutorApi = {
  getStatus: () => tutorFetch("/status"),
  getQuestions: () => tutorFetch("/questions"),
  getHistory: () => tutorFetch("/history"),
  ask: ({ message, question_id }) =>
    tutorFetch("/ask", {
      method: "POST",
      body: JSON.stringify({ message, question_id }),
    }),
  generate: (parameters) =>
    tutorFetch("/generate", {
      method: "POST",
      body: JSON.stringify(parameters),
    }),
  clearSession: () =>
    tutorFetch("/clear", {
      method: "POST",
    }),
};
