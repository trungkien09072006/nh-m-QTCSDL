let csrfToken = "";

async function request(path, options = {}) {
  const headers = new Headers(options.headers);
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method)) {
    if (!csrfToken) {
      await refreshCsrfToken();
    }
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || `Yêu cầu thất bại (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return body;
}

export async function refreshCsrfToken() {
  const response = await fetch("/api/csrf-token", {
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error("Không lấy được mã bảo vệ phiên. Hãy tải lại ứng dụng.");
  }
  const body = await response.json();
  csrfToken = body.csrf_token;
}

export const api = {
  session: () => request("/session"),
  login: async (email, password) => {
    const result = await request("/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    csrfToken = result.csrf_token;
    return result;
  },
  register: (fullname, email, password) =>
    request("/register", {
      method: "POST",
      body: JSON.stringify({ fullname, email, password }),
    }),
  logout: async () => {
    const result = await request("/logout", { method: "POST" });
    csrfToken = result.csrf_token;
    return result;
  },
  dashboard: () => request("/dashboard"),
  profile: () => request("/profile"),
  updateProfile: (profile) =>
    request("/profile", {
      method: "PUT",
      body: JSON.stringify(profile),
    }),
  exams: () => request("/exams"),
  startExam: (examId) =>
    request(`/exams/${examId}/attempts`, { method: "POST" }),
  getExamAttempt: (attemptId) => request(`/exam-attempts/${attemptId}`),
  saveExamAnswers: (attemptId, answers) =>
    request(`/exam-attempts/${attemptId}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
  submitExam: (attemptId, answers) =>
    request(`/exam-attempts/${attemptId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
};
