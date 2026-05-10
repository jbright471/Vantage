import { fireEvent, render, screen } from "@testing-library/react";

import { OnboardingPanel } from "./OnboardingPanel";


describe("OnboardingPanel", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders setup progress and opens the operator guide", () => {
    const onOpenDocs = vi.fn();

    render(
      <OnboardingPanel
        streamStatus="live"
        nodeCount={2}
        modelCount={3}
        runCount={1}
        routingRuleCount={2}
        onOpenDocs={onOpenDocs}
        onOpenSetupWizard={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Bring a new Vantage instance online" })).toBeTruthy();
    expect(screen.getByText("5/5")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Read operator guide" }));

    expect(onOpenDocs).toHaveBeenCalledTimes(1);
  });

  it("can be dismissed locally", () => {
    render(
      <OnboardingPanel
        streamStatus="connecting"
        nodeCount={0}
        modelCount={0}
        runCount={0}
        routingRuleCount={0}
        onOpenDocs={vi.fn()}
        onOpenSetupWizard={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(screen.queryByRole("heading", { name: "Bring a new Vantage instance online" })).toBeNull();
    expect(window.localStorage.getItem("vantage:onboarding-dismissed")).toBe("1");
  });

  it("opens the setup wizard from the primary action", () => {
    const onOpenSetupWizard = vi.fn();

    render(
      <OnboardingPanel
        streamStatus="live"
        nodeCount={1}
        modelCount={1}
        runCount={1}
        routingRuleCount={1}
        onOpenDocs={vi.fn()}
        onOpenSetupWizard={onOpenSetupWizard}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Launch setup wizard" }));

    expect(onOpenSetupWizard).toHaveBeenCalledTimes(1);
  });
});
