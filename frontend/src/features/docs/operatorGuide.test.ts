import { parseOperatorGuide } from "./operatorGuide";


describe("parseOperatorGuide", () => {
  it("creates a welcome page, one page per level-three heading, and a fallback for a level-two-only section", () => {
    const guide = parseOperatorGuide(
      [
        "# Vantage Operator Guide",
        "",
        "Intro copy.",
        "",
        "## Settings",
        "",
        "Shared settings context.",
        "",
        "### Polling",
        "",
        "Polling details.",
        "",
        "### Authentication",
        "",
        "Token details.",
        "",
        "## Operator Checklist",
        "",
        "- Back up the database.",
      ].join("\n"),
    );

    expect(guide.title).toBe("Vantage Operator Guide");
    expect(guide.groups.map((group) => group.title)).toEqual(["Start Here", "Settings", "Operator Checklist"]);
    expect(guide.pages.map((page) => page.slug)).toEqual([
      "welcome",
      "polling",
      "authentication",
      "operator-checklist",
    ]);
    expect(guide.pages[1].markdown).toContain("Shared settings context.");
    expect(guide.pages[1].markdown).toContain("Polling details.");
    expect(guide.pages[2].markdown).not.toContain("Shared settings context.");
    expect(guide.pages[3].markdown).toContain("Back up the database.");
  });

  it("ignores heading-shaped lines inside fenced code and keeps duplicate slugs unique", () => {
    const guide = parseOperatorGuide(
      [
        "# Guide",
        "",
        "## Tasks",
        "",
        "### Run Check",
        "",
        "```text",
        "### This is output, not navigation",
        "```",
        "",
        "#### Nested Detail",
        "",
        "### Run Check",
        "",
        "Second check.",
      ].join("\n"),
    );

    expect(guide.pages.map((page) => page.slug)).toEqual(["run-check", "run-check-2"]);
    expect(guide.pages[0].markdown).toContain("### This is output, not navigation");
    expect(guide.pages[0].markdown).toContain("### Nested Detail");
  });
});
