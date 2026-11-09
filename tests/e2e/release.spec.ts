import {
  test,
  expect,
  Page,
} from "../../apps/web/node_modules/@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
const marker = Date.now().toString().slice(-6);
async function login(page: Page, role = "operator") {
  await page.goto("/");
  await page.getByLabel("Workspace role").selectOption(role);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Evaluation runs", exact: true }),
  ).toBeVisible();
}
async function create(
  page: Page,
  fixture: "reference" | "regression",
  label: string,
  llm = false,
) {
  await page
    .getByRole("button", { name: "New evaluation", exact: true })
    .click();
  await page.getByLabel("Fixture output set").selectOption(fixture);
  await page.getByLabel("Run label").fill(label);
  if (llm) {
    const option = page
      .locator("#run-policy option")
      .filter({ hasText: "LLM required" });
    await page
      .getByLabel("Release policy")
      .selectOption((await option.first().getAttribute("value")) || "");
  }
  await page.getByRole("button", { name: "Start evaluation" }).click();
  await expect(
    page.getByRole("dialog", { name: "Evaluation details" }),
  ).toBeVisible();
  await expect(page.getByText("60 / 60 cases processed")).toBeVisible({
    timeout: 60000,
  });
  const dialog = page.getByRole("dialog", { name: "Evaluation details" });
  await expect(
    dialog.getByText(/fixture source · DEMO · completed/),
  ).toBeVisible();
  return dialog;
}
async function capture(page: Page, name: string) {
  if (process.env.CAPTURE_SCREENSHOTS === "1") {
    const dir = path.resolve("../../docs/screenshots");
    await fs.mkdir(dir, { recursive: true });
    await page.screenshot({
      path: path.join(dir, name + ".png"),
      fullPage: true,
    });
  }
}

test("reference → regression → paired comparison → evidence → reviewer approval", async ({
  page,
}) => {
  await login(page);
  const referenceLabel = `Reference ${marker}`,
    regressionLabel = `Regression ${marker}`;
  const reference = await create(page, "reference", referenceLabel);
  await expect(reference.locator(".job-title .badge")).toHaveText("approved");
  await expect(reference.locator(".job-stats")).toContainText("100%");
  await expect(
    reference.getByRole("button", { name: "Record approval" }),
  ).toHaveCount(0);
  const download = page.waitForEvent("download");
  await reference.getByRole("link", { name: "JSON", exact: true }).click();
  expect((await download).suggestedFilename()).toContain(".json");
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  const regression = await create(page, "regression", regressionLabel);
  await expect(regression.locator(".job-title .badge")).toHaveText("rejected");
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await capture(page, "evaluation-runs-desktop");
  await page.getByRole("button", { name: "Compare versions" }).click();
  const baselineOption = page
    .locator("#baseline option")
    .filter({ hasText: referenceLabel });
  await page
    .getByLabel("Baseline run")
    .selectOption((await baselineOption.getAttribute("value")) || "");
  const candidateOption = page
    .locator("#candidate option")
    .filter({ hasText: regressionLabel });
  await page
    .getByLabel("Candidate run")
    .selectOption((await candidateOption.getAttribute("value")) || "");
  await page.getByRole("button", { name: "Compare runs", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Regressions to investigate" }),
  ).toBeVisible();
  await expect(page.getByText("Regression detected").first()).toBeVisible();
  await capture(page, "comparison-desktop");
  await page.getByRole("button", { name: "Open candidate" }).click();
  await page
    .getByRole("button", { name: /Inspect / })
    .first()
    .click();
  await expect(page.getByText("Output under evaluation")).toBeVisible();
  await page.getByRole("button", { name: "Close case details" }).click();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByLabel("Workspace role").selectOption("reviewer");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Evaluation runs", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "New evaluation", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: `Open ${referenceLabel}`, exact: true })
    .click();
  await page.getByRole("button", { name: "Record approval" }).click();
  await page
    .getByLabel("Approval note")
    .fill("Reviewed deterministic fixture checks and provenance.");
  await page
    .getByRole("button", { name: "Confirm approval", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Release approval recorded",
  );
  await page
    .getByRole("button", { name: /Inspect / })
    .first()
    .click();
  await page
    .getByLabel("Reason for correction")
    .fill("Human review confirms the supplied expected citation.");
  await page.getByRole("button", { name: "Save human review" }).click();
  await expect(page.getByRole("status")).toContainText("Human review recorded");
});

test("mandatory LLM evaluation remains pending without credentials", async ({
  page,
}) => {
  await login(page);
  const dialog = await create(page, "reference", `LLM pending ${marker}`, true);
  await expect(dialog.locator(".job-title .badge")).toHaveText("inconclusive");
  await expect(dialog.locator(".job-stats")).toContainText("60");
  await page
    .getByRole("button", { name: /Inspect / })
    .first()
    .click();
  await expect(page.getByRole("dialog").last()).toContainText("pending");
  await capture(page, "pending-evaluation");
});

test("viewer role, dataset inspection, keyboard dialog focus and mobile layout", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "viewer");
  await expect(
    page.getByRole("button", { name: "New evaluation", exact: true }),
  ).toHaveCount(0);
  await capture(page, "evaluation-runs-mobile");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Dataset library" }).click();
  await expect(
    page.getByRole("button", { name: "Import dataset", exact: true }),
  ).toHaveCount(0);
  await page.locator(".dataset-card").first().click();
  await expect(
    page.getByRole("dialog", { name: "Dataset details" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close dialog", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.viewport);
});

test("invalid imported outputs are explained without losing form input", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "Import outputs" }).click();
  await page.getByLabel("Output records").fill('{"invalid":true}');
  await page.getByRole("button", { name: "Validate and import" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Output records")).toHaveValue(
    '{"invalid":true}',
  );
});

test("operator creates an immutable release policy version", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "Dataset library" }).click();
  await page.getByRole("button", { name: "New policy version" }).click();
  await page
    .getByLabel("Policy name", { exact: true })
    .fill(`Reviewed policy ${marker}`);
  await page.getByLabel("Required case pass rate (%)").fill("95");
  await page
    .getByLabel("Required evaluation", { exact: true })
    .selectOption("llm");
  await page.getByLabel("Rubric version").fill("human-grounding-v2");
  await page
    .getByRole("button", { name: "Create policy version", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Release policy version created",
  );
  await expect(
    page
      .locator(".config-row")
      .filter({ hasText: `Reviewed policy ${marker}` }),
  ).toContainText("Threshold 95%");
  await expect(
    page
      .locator(".config-row")
      .filter({ hasText: `Reviewed policy ${marker}` }),
  ).toContainText("LLM review required");
});
