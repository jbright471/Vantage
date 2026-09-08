import { act, renderHook, waitFor } from "@testing-library/react";

import { useEventSource } from "./useEventSource";

class FakeEventSource {
  private listeners = new Map<string, Set<EventListenerOrEventListenerObject>>();
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.get(type)?.delete(listener);
  }

  emit(type: string, data: string) {
    const event = new MessageEvent(type, { data });
    for (const listener of this.listeners.get(type) ?? []) {
      if (typeof listener === "function") {
        listener(event);
      } else {
        listener.handleEvent(event);
      }
    }
  }
}

describe("useEventSource", () => {
  it("applies full state and deltas, then marks a connected stream as reconnecting", async () => {
    const source = new FakeEventSource();
    const createEventSource = () => source;
    const { result, unmount } = renderHook(() => useEventSource("/api/stream", createEventSource));

    act(() => {
      source.emit(
        "full_state",
        JSON.stringify({ nodes: [], runs: [], models: [], routing: [], warnings: [] }),
      );
    });
    await waitFor(() => expect(result.current.streamStatus).toBe("live"));

    act(() => {
      source.emit("delta", JSON.stringify({ runs: [{ run_id: "run-1", summary: "Observed", status: "success", node_id: "control-plane", started_at: null }] }));
    });
    await waitFor(() => expect(result.current.state.runs).toHaveLength(1));

    act(() => source.onerror?.(new Event("error")));
    expect(result.current.streamStatus).toBe("reconnecting");

    unmount();
    expect(source.close).toHaveBeenCalledOnce();
  });

  it("marks a stream failure before the first full state as an error", () => {
    const source = new FakeEventSource();
    const createEventSource = () => source;
    const { result } = renderHook(() => useEventSource("/api/stream", createEventSource));

    act(() => source.onerror?.(new Event("error")));

    expect(result.current.streamStatus).toBe("error");
  });
});
