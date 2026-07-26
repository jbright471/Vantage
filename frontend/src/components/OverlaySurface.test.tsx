import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { OverlayHeader, OverlaySurface } from "./OverlaySurface";

function OverlayHarness({ onClose = vi.fn() }: { onClose?: () => void }) {
  return (
    <OverlaySurface isOpen onClose={onClose} labelledBy="test-overlay-title">
      <OverlayHeader
        titleId="test-overlay-title"
        title="Test overlay"
        closeLabel="Close test overlay"
        onClose={onClose}
      />
      <button type="button">First action</button>
      <button type="button">Last action</button>
    </OverlaySurface>
  );
}

describe("OverlaySurface", () => {
  it("stays out of the DOM when closed", () => {
    render(
      <OverlaySurface isOpen={false} onClose={vi.fn()} labelledBy="closed-title">
        <h2 id="closed-title">Closed overlay</h2>
      </OverlaySurface>,
    );

    expect(screen.queryByRole("dialog", { name: "Closed overlay" })).toBeNull();
  });

  it("locks scrolling and closes with Escape", () => {
    const onClose = vi.fn();
    render(<OverlayHarness onClose={onClose} />);

    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("dismisses only when a pointer press and release both land on the backdrop", () => {
    const onClose = vi.fn();
    render(<OverlayHarness onClose={onClose} />);
    const backdrop = document.querySelector<HTMLElement>(".overlay-backdrop");
    const surface = screen.getByRole("dialog", { name: "Test overlay" });

    expect(backdrop).toBeTruthy();
    fireEvent.pointerDown(surface);
    fireEvent.pointerUp(backdrop as HTMLElement);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.pointerDown(backdrop as HTMLElement);
    fireEvent.pointerUp(backdrop as HTMLElement);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("wraps keyboard focus within the surface", () => {
    render(<OverlayHarness />);
    const firstAction = screen.getByRole("button", { name: "Close test overlay" });
    const lastAction = screen.getByRole("button", { name: "Last action" });

    lastAction.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(firstAction);

    firstAction.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(lastAction);
  });

  it("restores focus to the trigger after closing", () => {
    function RestoreFocusHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Open overlay
          </button>
          <OverlaySurface isOpen={open} onClose={() => setOpen(false)} labelledBy="restore-title">
            <h2 id="restore-title">Restore overlay</h2>
            <button type="button" onClick={() => setOpen(false)}>
              Finish
            </button>
          </OverlaySurface>
        </>
      );
    }

    render(<RestoreFocusHarness />);
    const trigger = screen.getByRole("button", { name: "Open overlay" });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));

    expect(document.activeElement).toBe(trigger);
  });
});
