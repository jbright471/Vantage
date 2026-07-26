import { apiFetch } from "./http";

describe("apiFetch", () => {
  afterEach(() => {
    document.cookie = "vantage_csrf=; Max-Age=0; path=/";
    vi.restoreAllMocks();
  });

  it("adds the session CSRF token to state-changing requests", async () => {
    document.cookie = "vantage_csrf=csrf-test-token; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    await apiFetch("/api/actions/refresh-node/control-plane", {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    const [, request] = fetchMock.mock.calls[0];
    expect(request?.credentials).toBe("same-origin");
    expect(new Headers(request?.headers).get("X-Vantage-CSRF")).toBe("csrf-test-token");
    expect(new Headers(request?.headers).get("Accept")).toBe("application/json");
  });

  it("does not add CSRF metadata to read-only requests", async () => {
    document.cookie = "vantage_csrf=csrf-test-token; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    const request = { headers: { Accept: "application/json" } };

    await apiFetch("/api/nodes", request);

    expect(fetchMock).toHaveBeenCalledWith("/api/nodes", request);
  });
});
