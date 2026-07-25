import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AuthGate } from "./AuthGate";


function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AuthGate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("unlocks the control plane without persisting the operator token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ configured: true, authenticated: false }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }));

    render(
      <AuthGate>
        <h1>Operator console</h1>
      </AuthGate>,
    );

    const tokenInput = await screen.findByLabelText("Operator token");
    const operatorToken = "operator-token-value-0000000000000000";
    fireEvent.change(tokenInput, { target: { value: operatorToken } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock Vantage" }));

    expect(await screen.findByRole("heading", { name: "Operator console" })).toBeTruthy();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        body: JSON.stringify({ token: operatorToken }),
        credentials: "same-origin",
      }),
    );
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("explains how to configure a locked-down instance", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ configured: false, authenticated: false }),
    );

    render(
      <AuthGate>
        <h1>Operator console</h1>
      </AuthGate>,
    );

    expect(await screen.findByRole("heading", { name: "Secure setup required" })).toBeTruthy();
    expect(screen.getByText("VANTAGE_CONTROL_PLANE_TOKEN", { exact: false })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Operator console" })).toBeNull();
  });

  it("shows a generic error after rejected credentials", async () => {
    vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ configured: true, authenticated: false }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Control-plane authentication failed" }, 401));

    render(
      <AuthGate>
        <h1>Operator console</h1>
      </AuthGate>,
    );

    fireEvent.change(await screen.findByLabelText("Operator token"), { target: { value: "wrong-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock Vantage" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Unlock failed");
    });
  });
});
