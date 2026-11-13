import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "../../apps/web/node_modules/@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

type Case = { id: string; context: string; [key: string]: unknown };
type Output = { case_id: string; output: Record<string, unknown> };
type Job = {
  id: string;
  status: string;
  summary: { passed: number; pending: number; total: number };
};
const root = path.resolve("../..");
async function records() {
  const cases: Case[] = JSON.parse(
    await fs.readFile(path.join(root, "fixtures/cases.json"), "utf8"),
  );
  const outputs: Output[] = JSON.parse(
    await fs.readFile(path.join(root, "fixtures/reference.json"), "utf8"),
  );
  return { cases: cases.slice(0, 2), outputs: outputs.slice(0, 2) };
}
async function setup(request: APIRequestContext) {
  await expect(
    await request.post("/api/auth/login", {
      data: { username: "operator", password: "demo-release" },
    }),
  ).toBeOK();
  const response = await request.get("/api/configurations");
  await expect(response).toBeOK();
  const gate = (await response.json()).find(
    (c: { name: string; require_llm: boolean }) =>
      c.name === "Deterministic gate" && !c.require_llm,
  );
  expect(gate).toBeTruthy();
  return gate.id as string;
}
async function dataset(request: APIRequestContext, cases: Case[]) {
  const response = await request.post("/api/datasets/import", {
    data: {
      name: `Audit contract ${randomUUID()}`,
      version: "1",
      format: "json",
      content: JSON.stringify(cases),
    },
  });
  await expect(response).toBeOK();
  return (await response.json()).id as string;
}
async function evaluate(
  request: APIRequestContext,
  datasetId: string,
  configuration: string,
  outputs: Output[],
  label: string,
): Promise<Job> {
  const response = await request.post("/api/jobs/import", {
    data: {
      dataset_id: datasetId,
      configuration_id: configuration,
      label,
      format: "json",
      content: JSON.stringify(outputs),
    },
  });
  await expect(response).toBeOK();
  const created: Job = await response.json();
  let result = created;
  await expect
    .poll(async () => {
      const progress = await request.get(`/api/jobs/${created.id}`);
      await expect(progress).toBeOK();
      result = await progress.json();
      return result.status;
    })
    .toBe("completed");
  return result;
}
async function compare(page: Page, baseline: string, candidate: string) {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Evaluation runs", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Compare versions" }).click();
  await expect(
    page.getByText("See the change behind the score."),
  ).toBeVisible();
  await page.getByLabel("Baseline run").selectOption(baseline);
  await page.getByLabel("Candidate run").selectOption(candidate);
  await page.getByRole("button", { name: "Compare runs", exact: true }).click();
  await expect(page.locator(".compare-metrics")).toBeVisible();
}
async function capture(page: Page, name: string) {
  if (process.env.CAPTURE_SCREENSHOTS !== "1") return;
  const dir = path.join(root, "docs/screenshots");
  await fs.mkdir(dir, { recursive: true });
  await page.screenshot({
    path: path.join(dir, `audit-${name}.png`),
    fullPage: (page.viewportSize()?.width ?? 1440) >= 600,
  });
}
function metric(page: Page, label: string) {
  return page
    .locator(".compare-metrics .metric")
    .filter({ has: page.getByText(label, { exact: true }) });
}

test("missing output is pending, not zero movement or a measured regression", async ({
  page,
}) => {
  const config = await setup(page.request);
  const { cases, outputs } = await records();
  const suite = await dataset(page.request, cases);
  const baseline = await evaluate(
    page.request,
    suite,
    config,
    outputs,
    "Audit complete reference",
  );
  const candidate = await evaluate(
    page.request,
    suite,
    config,
    outputs.slice(0, 1),
    "Audit missing output",
  );
  expect(baseline.summary).toMatchObject({ passed: 2, pending: 0, total: 2 });
  expect(candidate.summary).toMatchObject({ passed: 1, pending: 1, total: 2 });
  await compare(page, baseline.id, candidate.id);
  await expect(metric(page, "Paired cases").locator("strong")).toHaveText("2");
  await expect(metric(page, "Pass rate change").locator("strong")).toHaveText(
    "Pending",
  );
  await expect(metric(page, "Pass rate change")).toContainText(
    "1 pairs lack completed evidence",
  );
  await expect(metric(page, "Regressions").locator("strong")).toHaveText("0");
  await expect(page.getByText("0 pp", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("Regression detected", { exact: true }),
  ).toHaveCount(0);
  await capture(page, "pending-comparison");
});

test("changed evidence for the same case identifier is visibly excluded", async ({
  page,
}) => {
  const config = await setup(page.request);
  const { cases, outputs } = await records();
  const original = await dataset(page.request, cases.slice(0, 1));
  const changed = await dataset(page.request, [
    {
      ...cases[0],
      context: `${cases[0].context} A new paragraph changes this case contract.`,
    },
  ]);
  const baseline = await evaluate(
    page.request,
    original,
    config,
    outputs.slice(0, 1),
    "Audit original contract",
  );
  const candidate = await evaluate(
    page.request,
    changed,
    config,
    outputs.slice(0, 1),
    "Audit changed contract",
  );
  await compare(page, baseline.id, candidate.id);
  await expect(metric(page, "Paired cases").locator("strong")).toHaveText("0");
  await expect(metric(page, "Unpaired cases").locator("strong")).toHaveText(
    "1",
  );
  await expect(
    page.getByRole("region", { name: "Comparison limitations" }),
  ).toContainText(`Changed case contracts excluded: ${cases[0].id}`);
  await expect(metric(page, "Pass rate change").locator("strong")).toHaveText(
    "Pending",
  );
  await capture(page, "incompatible-comparison");
});

test("mobile import shows a real validation error and recovers with keyboard focus intact", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const config = await setup(page.request);
  const { cases, outputs } = await records();
  const suite = await dataset(page.request, cases);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Evaluation runs", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Compare versions" }).click();
  await expect(
    page.getByText("See the change behind the score."),
  ).toBeVisible();
  await capture(page, "mobile-empty-comparison");
  await page.getByRole("button", { name: /^Evaluation runs/ }).click();
  await page
    .getByRole("button", { name: "Import outputs", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Close dialog", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Run label", { exact: true })).toBeFocused();
  expect(
    await page
      .getByLabel("Run label", { exact: true })
      .evaluate((el) => getComputedStyle(el).outlineStyle),
  ).not.toBe("none");
  await page
    .getByLabel("Run label", { exact: true })
    .fill("Audit mobile recovery");
  await page.getByLabel("Dataset", { exact: true }).selectOption(suite);
  await page.getByLabel("Policy", { exact: true }).selectOption(config);
  await page
    .getByLabel("Output records", { exact: true })
    .fill('{"invalid":true}');
  // Delay only delivery of the real backend response to inspect loading; fabricate no response data.
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/api/jobs/import",
    async (route) => {
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response });
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Validate and import", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Validating…", exact: true }),
  ).toBeDisabled();
  await capture(page, "mobile-loading");
  release();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeInViewport();
  await expect(page.getByLabel("Output records", { exact: true })).toHaveValue(
    '{"invalid":true}',
  );
  await capture(page, "mobile-validation-error");
  await page
    .getByLabel("Output records", { exact: true })
    .fill(JSON.stringify(outputs));
  await page
    .getByRole("button", { name: "Validate and import", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Evaluation details" }),
  ).toBeVisible();
  await expect(page.getByText("2 / 2 cases processed")).toBeVisible();
  await expect(page.locator(".job-title .badge")).toHaveText("approved");
  await capture(page, "mobile-recovered");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});
