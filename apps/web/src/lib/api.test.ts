import { describe, it, expect, vi, afterEach } from "vitest";
import { api, tone, percentage } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("API client", () => {
  it("surfaces safe server errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          json: async () => ({ detail: "Reviewer role required" }),
        }),
    );
    await expect(api("/jobs/a/approve", {})).rejects.toThrow(
      "Reviewer role required",
    );
  });
  it("posts JSON on same origin with session cookie", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: "job-1" }),
      });
    vi.stubGlobal("fetch", fetcher);
    await expect(api("/jobs", { source: "fixture" })).resolves.toEqual({
      id: "job-1",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/jobs",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: '{"source":"fixture"}',
      }),
    );
  });
  it("keeps pending distinct from a release approval", () => {
    expect(tone("inconclusive")).toBe("amber");
    expect(tone("rejected")).toBe("red");
    expect(percentage(undefined)).toBe("—");
    expect(percentage(0)).toBe("0%");
  });
});
