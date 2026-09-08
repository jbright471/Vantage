import { expect, test, type Page } from "@playwright/test";

async function unlockOperatorConsole(page: Page, operatorToken: string) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Unlock operator console" })).toBeVisible();
  await page.getByLabel("Operator token").fill(operatorToken);
  await page.getByRole("button", { name: "Unlock Vantage" }).click();
  await expect(page.getByRole("heading", { name: "Local AI Command Center" })).toBeVisible();
}

function captureBrowserErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test("external operator can unlock, observe, refresh, export, and lock Vantage", async ({ page }) => {
  const browserErrors = captureBrowserErrors(page);
  const operatorToken = process.env.VANTAGE_CONTROL_PLANE_TOKEN;
  test.skip(!operatorToken, "Set VANTAGE_CONTROL_PLANE_TOKEN to run the authenticated smoke test.");

  await unlockOperatorConsole(page, operatorToken!);
  await expect(page.getByText("LOCAL / DESKTOP / VANTAGE")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Machine health across your local fleet" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Merged inventory across every registered node" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Preferred node order for each policy lane" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Measure local model behavior" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Control Plane", level: 3 }).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Current observation").first()).toBeVisible({ timeout: 20_000 });
  if (process.env.VANTAGE_E2E_DASHBOARD_SCREENSHOT_PATH) {
    await page.screenshot({ path: process.env.VANTAGE_E2E_DASHBOARD_SCREENSHOT_PATH, fullPage: true, animations: "disabled" });
  }

  await page.getByRole("button", { name: "Docs" }).click();
  const docs = page.getByRole("dialog", { name: "Operator Guide" });
  await expect(docs.getByRole("heading", { name: "Welcome", level: 2 })).toBeVisible();
  await expect(page).toHaveURL(/\?docs=welcome$/);

  await docs.getByRole("link", { name: "Polling and Freshness" }).click();
  await expect(docs.getByRole("heading", { name: "Polling and Freshness", level: 2 })).toBeVisible();
  await expect(page).toHaveURL(/\?docs=polling-and-freshness$/);

  await page.reload();
  await expect(page.getByRole("dialog", { name: "Operator Guide" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Polling and Freshness", level: 2 })).toBeVisible();
  if (process.env.VANTAGE_E2E_SCREENSHOT_PATH) {
    await page.screenshot({ path: process.env.VANTAGE_E2E_SCREENSHOT_PATH, animations: "disabled" });
  }

  await page.getByRole("searchbox", { name: "Search guide" }).fill("backup sqlite");
  await expect(page.getByRole("link", { name: "Back Up SQLite Before Updating" })).toBeVisible();
  await page.getByRole("link", { name: "Back Up SQLite Before Updating" }).click();
  await expect(page).toHaveURL(/\?docs=back-up-sqlite-before-updating$/);

  await page.goBack();
  await expect(page.getByRole("heading", { name: "Polling and Freshness", level: 2 })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: "Back Up SQLite Before Updating", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Close operator guide" }).click();
  await expect(page).not.toHaveURL(/\?docs=/);

  await page.getByRole("button", { name: "Launch setup wizard" }).click();
  const setup = page.getByRole("dialog", { name: "First-run setup wizard" });
  await expect(setup).toContainText("VANTAGE_CONTROL_PLANE_TOKEN=");
  await expect(setup).toContainText("VANTAGE_SESSION_SIGNING_KEY=");
  await expect(setup).toContainText("VANTAGE_AGENT_AUTH_MODE=hmac");
  await setup.getByRole("button", { name: "Next" }).click();
  await setup.getByLabel("Node name").fill("Render Worker");
  await expect(setup).toContainText('node_id = "render-worker"');
  await expect(setup).toContainText("Linux agent install");
  await expect(setup).toContainText("VANTAGE_AGENT_CONTROL_PLANE_CIDRS");
  await expect(setup).toContainText("allow TCP 9110 only from the control-plane");
  await expect(setup).toContainText("Vantage does not scan the LAN");
  await page.keyboard.press("Escape");
  await expect(setup).toBeHidden();

  const controlPlaneCard = page.locator("article").filter({ hasText: "Control Plane" });
  await controlPlaneCard.getByRole("button", { name: "Refresh node" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Refresh verified" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Refresh node control-plane verified").first()).toBeVisible({ timeout: 20_000 });

  const exports = await page.evaluate(async () =>
    Promise.all(
      ["/api/runs/export.json", "/api/runs/export.csv", "/api/evals/export.json", "/api/evals/export.csv"].map(
        async (url) => {
          const response = await fetch(url);
          return { url, status: response.status, contentType: response.headers.get("content-type") };
        },
      ),
    ),
  );
  expect(exports).toEqual([
    expect.objectContaining({ url: "/api/runs/export.json", status: 200, contentType: "application/json" }),
    expect.objectContaining({ url: "/api/runs/export.csv", status: 200, contentType: expect.stringContaining("text/csv") }),
    expect.objectContaining({ url: "/api/evals/export.json", status: 200, contentType: "application/json" }),
    expect.objectContaining({ url: "/api/evals/export.csv", status: 200, contentType: expect.stringContaining("text/csv") }),
  ]);

  await page.getByRole("button", { name: "Lock session" }).click();
  await expect(page.getByRole("heading", { name: "Unlock operator console" })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test("compact desktop layout preserves navigation and overlay boundaries", async ({ page }) => {
  const browserErrors = captureBrowserErrors(page);
  const operatorToken = process.env.VANTAGE_CONTROL_PLANE_TOKEN;
  test.skip(!operatorToken, "Set VANTAGE_CONTROL_PLANE_TOKEN to run the authenticated smoke test.");
  await page.setViewportSize({ width: 1024, height: 800 });
  await unlockOperatorConsole(page, operatorToken!);

  const evalNavLink = page.getByRole("link", { name: /Eval Lab/ });
  await evalNavLink.click();
  await expect(evalNavLink).toHaveAttribute("aria-current", "location");
  await expect(page.getByRole("heading", { name: "Measure local model behavior" })).toBeVisible();

  await expect(page.getByText("Loading eval suites…")).toBeHidden();
  const installStarterSuiteButton = page.getByRole("button", { name: "Install starter suite", exact: true });
  if (await installStarterSuiteButton.isVisible()) {
    await installStarterSuiteButton.click();
  }
  await expect(page.getByRole("button", { name: "Starter suite installed" })).toBeDisabled();
  await expect(page.getByRole("cell", { name: "Vantage Starter Smoke" }).first()).toBeVisible();

  const documentFitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(documentFitsViewport).toBe(true);

  await page.getByRole("button", { name: "Docs" }).click();
  const docs = page.getByRole("dialog", { name: "Operator Guide" });
  await expect(docs).toBeVisible();
  const docsBox = await docs.boundingBox();
  expect(docsBox).not.toBeNull();
  expect((docsBox?.x ?? 0) + (docsBox?.width ?? 0)).toBeLessThanOrEqual(1024);
  await page.getByRole("button", { name: "Close operator guide" }).click();

  await page.getByRole("button", { name: "Lock session" }).click();
  await expect(page.getByRole("heading", { name: "Unlock operator console" })).toBeVisible();
  expect(browserErrors).toEqual([]);
});
