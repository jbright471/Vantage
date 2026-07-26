import { summarizeAttention } from "./App";

describe("summarizeAttention", () => {
  it("does not treat disabled nodes as actionable fleet signals", () => {
    expect(
      summarizeAttention(
        [
          { enabled: true, observed_status: "healthy", freshness: "live" },
          { enabled: false, observed_status: "unreachable", freshness: "stale" },
        ],
        0,
        0,
      ),
    ).toBe("All lanes nominal");
  });

  it("continues to report degraded and stale enabled nodes", () => {
    expect(
      summarizeAttention([{ enabled: true, observed_status: "degraded", freshness: "stale" }], 0, 0),
    ).toBe("2 signals need attention");
  });
});
