const CSRF_COOKIE_NAME = "vantage_csrf";
const CSRF_HEADER_NAME = "X-Vantage-CSRF";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function readCsrfToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${CSRF_COOKIE_NAME}=`;
  const value = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const csrfToken = SAFE_METHODS.has(method) ? null : readCsrfToken();

  if (!csrfToken) {
    return globalThis.fetch(input, init);
  }

  const headers = new Headers(init?.headers);
  headers.set(CSRF_HEADER_NAME, csrfToken);

  return globalThis.fetch(input, {
    ...init,
    credentials: init?.credentials ?? "same-origin",
    headers,
  });
}
