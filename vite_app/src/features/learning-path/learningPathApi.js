let csrfToken = "";

async function loadCsrfToken() {
  const response = await fetch("/api/csrf-token", { credentials: "same-origin" });
  if (!response.ok) {
    throw new Error("Không lấy được mã bảo vệ phiên. Hãy tải lại ứng dụng.");
  }
  csrfToken = (await response.json()).csrf_token || "";
}

async function call(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method)) {
    if (!csrfToken) {
      await loadCsrfToken();
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

export const learningPathApi = {
  get: () => call("/learning-path"),
  updateStatus: (itemId, status) =>
    call(`/learning-path/items/${itemId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};