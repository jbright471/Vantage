import { createContext, FormEvent, ReactNode, useContext, useEffect, useState } from "react";

import { readCsrfToken } from "../../api/http";

type AuthStatus = {
  configured: boolean;
  authenticated: boolean;
};

type AuthGateProps = {
  children: ReactNode;
};

type SessionActions = {
  lockSession: () => Promise<void>;
  error: string | null;
};

const SessionActionsContext = createContext<SessionActions | null>(null);

export function useSessionActions(): SessionActions | null {
  return useContext(SessionActionsContext);
}

async function readAuthStatus(): Promise<AuthStatus> {
  const response = await fetch("/api/auth/status", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("status-unavailable");
  }
  return response.json() as Promise<AuthStatus>;
}

export function AuthGate({ children }: AuthGateProps) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refreshStatus() {
    setError(null);
    try {
      setStatus(await readAuthStatus());
    } catch {
      setStatus(null);
      setError("Vantage could not reach the authentication service.");
    }
  }

  useEffect(() => {
    void refreshStatus();
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) {
        throw new Error("login-rejected");
      }
      setToken("");
      setStatus({ configured: true, authenticated: true });
    } catch {
      setToken("");
      setError("Unlock failed. Check the operator token and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    const csrf = readCsrfToken();
    setError(null);
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: csrf ? { "X-Vantage-CSRF": csrf } : {},
      });
      if (!response.ok) {
        throw new Error("logout-failed");
      }
      setStatus({ configured: true, authenticated: false });
    } catch {
      setError("Vantage could not lock the operator session.");
    }
  }

  if (status?.authenticated) {
    return (
      <SessionActionsContext.Provider value={{ lockSession: handleLogout, error }}>
        {children}
      </SessionActionsContext.Provider>
    );
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-live="polite">
        <p className="section-kicker">VANTAGE / CONTROL_PLANE</p>
        {status === null && !error ? (
          <>
            <h1>Checking operator session</h1>
            <p className="auth-copy">Establishing a secure connection to the local control plane.</p>
          </>
        ) : null}

        {status && !status.configured ? (
          <>
            <h1>Secure setup required</h1>
            <p className="auth-copy">
              Set <code>VANTAGE_CONTROL_PLANE_TOKEN</code> and <code>VANTAGE_SESSION_SIGNING_KEY</code> to independent,
              randomly generated values of at least 32 characters, then restart Vantage.
            </p>
          </>
        ) : null}

        {status?.configured && !status.authenticated ? (
          <>
            <h1>Unlock operator console</h1>
            <p className="auth-copy">The token is exchanged for a short-lived, HttpOnly browser session and is not stored.</p>
            <form className="auth-form" onSubmit={(event) => void handleLogin(event)}>
              <label className="visually-hidden" htmlFor="operator-identity">Operator identity</label>
              <input
                className="visually-hidden"
                id="operator-identity"
                name="username"
                type="text"
                autoComplete="username"
                readOnly
                value="operator"
                tabIndex={-1}
              />
              <label htmlFor="operator-token">Operator token</label>
              <input
                id="operator-token"
                name="operator-token"
                type="password"
                autoComplete="current-password"
                minLength={32}
                required
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
              <button type="submit" disabled={submitting}>
                {submitting ? "Unlocking…" : "Unlock Vantage"}
              </button>
            </form>
          </>
        ) : null}

        {error ? (
          <div className="auth-error" role="alert">
            <p>{error}</p>
            {status === null ? (
              <button type="button" onClick={() => void refreshStatus()}>Retry connection</button>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}
