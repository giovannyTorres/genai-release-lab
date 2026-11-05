import { afterEach, describe, expect, it, vi } from "vitest";
import { proxyToApi } from "./proxy";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
describe("runtime backend gateway", () => {
  it("reads API_URL at runtime, forwards session/origin, preserves export and cookie headers", async () => {
    vi.stubEnv("API_URL", "https://api.contoso.invalid");
    const transport = vi
      .fn()
      .mockResolvedValue(
        new Response("report", {
          headers: {
            "set-cookie":
              "release_session=opaque; HttpOnly; SameSite=Strict; Path=/",
            "content-disposition": "attachment; filename=report.json",
            "content-length": "6",
          },
        }),
      );
    vi.stubGlobal("fetch", transport);
    const result = await proxyToApi(
      new Request("https://lab.invalid/api/jobs/123/export?format=json", {
        headers: {
          cookie: "release_session=opaque",
          origin: "https://lab.invalid",
          host: "evil.invalid",
          "x-forwarded-host": "evil.invalid",
        },
      }),
      ["jobs", "123", "export"],
    );
    const [target, init] = transport.mock.calls[0];
    expect(target.toString()).toBe(
      "https://api.contoso.invalid/api/jobs/123/export?format=json",
    );
    expect(init.headers.get("cookie")).toBe("release_session=opaque");
    expect(init.headers.get("origin")).toBe("https://lab.invalid");
    expect(init.headers.has("host")).toBe(false);
    expect(init.headers.has("x-forwarded-host")).toBe(false);
    expect(init.redirect).toBe("manual");
    expect(result.headers.get("set-cookie")).toContain("HttpOnly");
    expect(result.headers.get("content-disposition")).toContain("report.json");
    expect(result.headers.has("content-length")).toBe(false);
    expect(await result.text()).toBe("report");
  });
  it("caps actual request bytes even with an absent content-length", async () => {
    const transport = vi.fn();
    vi.stubGlobal("fetch", transport);
    const result = await proxyToApi(
      new Request("http://localhost/api/datasets/import", {
        method: "POST",
        body: "x".repeat(2_100_001),
      }),
      ["datasets", "import"],
    );
    expect(result.status).toBe(413);
    expect(transport).not.toHaveBeenCalled();
  });
  it("does not expose backend connection errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("private backend credentials")),
    );
    const response = await proxyToApi(
      new Request("http://localhost/api/jobs"),
      ["jobs"],
    );
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("credentials");
  });
});
