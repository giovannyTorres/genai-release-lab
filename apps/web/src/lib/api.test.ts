import { describe, it, expect, vi, afterEach } from "vitest";
import { api, tone, percentage, releaseSignoff, type Job } from "./api";
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
  it("separates the automated gate from the human release approval", () => {
    const base: Job = {
      id: "j",
      label: "Reference",
      status: "completed",
      progress: 60,
      total: 60,
      decision: "approved",
      created_at: "",
      mode: "DEMO",
      source: "fixture",
      summary: { passed: 60, failed: 0, pending: 0, total: 60, pass_rate: 1 },
    };
    expect(releaseSignoff(base).text).toMatch(/A reviewer still has to record/);
    expect(
      releaseSignoff({
        ...base,
        approvals: [{ actor: "reviewer", comment: "Ready", created_at: "2026-11-09T10:00:00Z" }],
      }).text,
    ).toMatch(/Release approved by reviewer/);
    expect(
      releaseSignoff({ ...base, decision: "inconclusive", summary: { ...base.summary!, passed: 0, pending: 60 } }).text,
    ).toMatch(/60 mandatory checks have no result/);
    expect(
      releaseSignoff({ ...base, decision: "rejected", summary: { ...base.summary!, passed: 30, failed: 30 } }).text,
    ).toMatch(/30 of 60 cases failed/);
  });
});
