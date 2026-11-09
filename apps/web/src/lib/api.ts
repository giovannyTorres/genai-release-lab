export type User = { username: string; role: string };
export type ModeStatus = {
  mode: string;
  live: { ready: boolean; missing: string[] };
  fixture_notice: string;
};
export type Dataset = {
  id: string;
  name: string;
  version: string;
  hash: string;
  case_count: number;
  split_counts: Record<string, number>;
  created_at: string;
  cases?: Array<{
    id?: string;
    case_id?: string;
    split: string;
    prompt?: string;
    [key: string]: unknown;
  }>;
};
export type Configuration = {
  id: string;
  name: string;
  version: string;
  require_llm: boolean;
  threshold: number;
  hash: string;
};
export type Check = { status: string; detail: string };
export type Result = {
  case_id: string;
  split: string;
  prompt?: string;
  status: string;
  checks: Record<string, Check>;
  output: unknown;
  expected: unknown;
};
export type Job = {
  id: string;
  label: string;
  status: string;
  progress: number;
  total: number;
  decision: string;
  created_at: string;
  mode: string;
  source: string;
  summary?: {
    passed: number;
    total: number;
    failed: number;
    pending: number;
    pass_rate: number;
  };
  results?: Result[];
  error?: string;
  approvals?: Approval[];
  reviews?: HumanReview[];
  [key: string]: unknown;
};
export type Approval = { actor: string; comment: string; created_at: string };
export type HumanReview = {
  case_id: string;
  verdict: string;
  comment: string;
  actor: string;
  created_at: string;
};
export type Comparison = {
  baseline_id: string;
  candidate_id: string;
  paired: number;
  total_baseline: number;
  total_candidate: number;
  missing_baseline: string[];
  missing_candidate: string[];
  regressions: Array<{
    case_id: string;
    baseline: unknown;
    candidate: unknown;
  }>;
  improvements: unknown[];
  delta_pass_rate: number | null;
  incompatible_cases: string[];
  unprocessed_baseline: string[];
  unprocessed_candidate: string[];
  pending_pairs: number;
  same_configuration: boolean;
  same_evaluator: boolean;
};
export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Request could not be completed." }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Please check the submitted information.",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export function tone(status: string) {
  if (["approved", "pass", "passed", "completed"].includes(status))
    return "green";
  if (["rejected", "fail", "failed", "error"].includes(status)) return "red";
  return "amber";
}
export function percentage(value: number | undefined) {
  return value === undefined ? "—" : `${Math.round(value * 100)}%`;
}
export function shortId(id: string) {
  return id.slice(0, 8);
}
export function humanStatus(value: string | undefined) {
  return (value || "pending").replaceAll("_", " ");
}
/** Explains the release state: automated gate decision first, then the human sign-off it allows. */
export function releaseSignoff(job: Job): { tone: string; text: string } {
  const approvals = job.approvals ?? [];
  const summary = job.summary;
  if (job.status !== "completed")
    return {
      tone: "pending",
      text: "Evaluation in progress. Release approval is available only after a completed run.",
    };
  if (job.decision === "approved" && approvals.length) {
    const last = approvals[approvals.length - 1];
    return {
      tone: "pass",
      text: `Release approved by ${last.actor} on ${new Date(last.created_at).toLocaleString()}: “${last.comment}”`,
    };
  }
  if (job.decision === "approved")
    return {
      tone: "pending",
      text: "Automated gate passed. A reviewer still has to record the release approval.",
    };
  if (job.decision === "rejected")
    return {
      tone: "fail",
      text: `Rejected by the release gate: ${summary?.failed ?? 0} of ${summary?.total ?? job.total} cases failed. Release approval is blocked.`,
    };
  return {
    tone: "pending",
    text: `Inconclusive: ${summary?.pending ?? 0} mandatory checks have no result (for example, an LLM evaluation that needs LIVE). Release approval is blocked until evidence exists.`,
  };
}
/** Readable summary of a case's checks: which ones did not pass, instead of unlabeled dots. */
export function checkSummary(checks: Record<string, Check>): {
  tone: string;
  text: string;
} {
  const entries = Object.entries(checks);
  const name = (key: string) => {
    const text = humanStatus(key).replace(/\bllm\b/i, "LLM");
    return text.charAt(0).toUpperCase() + text.slice(1);
  };
  const failed = entries.filter(([, c]) => c.status === "fail").map(([k]) => name(k));
  const pending = entries.filter(([, c]) => c.status === "pending").map(([k]) => name(k));
  if (failed.length) return { tone: "fail", text: `${failed.join(", ")} failed` };
  if (pending.length) return { tone: "pending", text: `${pending.join(", ")} pending` };
  return { tone: "pass", text: `All ${entries.length} checks pass` };
}
