import { test, expect } from "../../apps/web/node_modules/@playwright/test";

// Browser contract tests: LIVE status and the login response are intercepted.
// These tests verify the form/request boundary, not external credentials or model APIs.
test("LIVE login accepts provisioned usernames without demo credentials", async ({
  page,
}) => {
  await page.route("**/api/status", (route) =>
    route.fulfill({
      json: {
        mode: "LIVE",
        live: { ready: false, missing: ["OPENAI_API_KEY"] },
        fixture_notice: "",
      },
    }),
  );
  let submitted: unknown;
  await page.route("**/api/auth/login", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 401,
      json: { detail: "Credentials were not accepted." },
    });
  });
  await page.goto("/");
  await expect(page.getByText("LIVE MODE", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Workspace role")).toHaveCount(0);
  await expect(page.getByText("demo-release", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("Choose a demo role", { exact: false }),
  ).toHaveCount(0);
  await page.getByLabel("Username", { exact: true }).fill("operator-live");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-contract-password");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Credentials were not accepted.",
  );
  expect(submitted).toEqual({
    username: "operator-live",
    password: "synthetic-contract-password",
  });
  await expect(page.getByText("LIVE MODE", { exact: true })).toBeVisible();
});

for (const failure of ["unavailable", "invalid-mode"] as const) {
  test(`status ${failure} remains UNKNOWN until a successful retry`, async ({
    page,
  }) => {
    await page.route(
      "**/api/status",
      (route) =>
        route.fulfill(
          failure === "unavailable"
            ? {
                status: 503,
                json: { detail: "Status temporarily unavailable." },
              }
            : {
                json: { mode: "STAGING", live: { ready: false, missing: [] } },
              },
        ),
      { times: 1 },
    );
    await page.goto("/");
    await expect(page.getByText("UNKNOWN MODE", { exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Workspace mode could not be confirmed",
    );
    await expect(page.getByText("DEMO MODE", { exact: true })).toHaveCount(0);
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
    await expect(page.getByLabel("Workspace role")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Enter workspace" }),
    ).toHaveCount(0);
    await expect(page.getByText("demo-release", { exact: true })).toHaveCount(
      0,
    );
    await page.getByRole("button", { name: "Retry connection" }).click();
    // The retry is served by the actual DEMO backend, and its normal login still works.
    await expect(page.getByText("DEMO MODE", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Demo password", { exact: true })).toHaveValue(
      "demo-release",
    );
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await expect(
      page.getByRole("heading", { name: "Evaluate. Compare. Decide." }),
    ).toBeVisible();
  });
}
