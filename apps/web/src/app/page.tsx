"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  Configuration,
  Dataset,
  Job,
  ModeStatus,
  User,
  Comparison,
  Result,
  percentage,
  checkSummary,
  releaseSignoff,
  shortId,
  tone,
  humanStatus,
} from "@/lib/api";

type Tab = "runs" | "datasets" | "compare";
function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    stack: (
      <>
        <path d="m3 7 9-4 9 4-9 4-9-4Z" />
        <path d="m3 12 9 4 9-4M3 17l9 4 9-4" />
      </>
    ),
    compare: (
      <>
        <path d="M8 3v18M16 3v18M4 7h8M12 17h8" />
        <circle cx="8" cy="7" r="2" />
        <circle cx="16" cy="17" r="2" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14m-6-6 6 6-6 6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />
      </>
    ),
    play: <path d="m8 4 12 8-12 8V4Z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    file: (
      <>
        <path d="M14 3H5v18h14V8l-5-5Z" />
        <path d="M14 3v5h5M8 12h8M8 16h5" />
      </>
    ),
    logout: (
      <>
        <path d="M9 4H4v16h5M9 12h12m-5-5 5 5-5 5" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7v1" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.grid}
    </svg>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d="M7 5h18v7H14v8h11v7H7V5Z" fill="currentColor" />
          <path className="brand-accent" d="M18 15h7v12h-7z" />
        </svg>
      </span>
      <span>
        RELEASE <strong>LAB</strong>
        <small>GenAI quality workspace</small>
      </span>
    </div>
  );
}
function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${tone(value)}`}>
      <span className="status-dot" />
      {humanStatus(value)}
    </span>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Icon name="stack" size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null),
    [status, setStatus] = useState<ModeStatus | null>(null),
    [booting, setBooting] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [loginRole, setLoginRole] = useState("operator"),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState("");
  const [tab, setTab] = useState<Tab>("runs"),
    [datasets, setDatasets] = useState<Dataset[]>([]),
    [configs, setConfigs] = useState<Configuration[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [job, setJob] = useState<Job | null>(null),
    [dataset, setDataset] = useState<Dataset | null>(null);
  const [runSource, setRunSource] = useState("api"),
    [endpointId, setEndpointId] = useState("");
  const [createOpen, setCreateOpen] = useState(false),
    [fixture, setFixture] = useState("reference"),
    [label, setLabel] = useState("Reference evaluation"),
    [datasetId, setDatasetId] = useState(""),
    [configId, setConfigId] = useState("");
  const [baseline, setBaseline] = useState(""),
    [candidate, setCandidate] = useState(""),
    [comparison, setComparison] = useState<Comparison | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [policyName, setPolicyName] = useState("");
  const [policyVersion, setPolicyVersion] = useState("1");
  const [policyThreshold, setPolicyThreshold] = useState("100");
  const [policyLlm, setPolicyLlm] = useState(false);
  const [policyProvider, setPolicyProvider] = useState("openai");
  const [policyModel, setPolicyModel] = useState("gpt-4.1-mini");
  const [policyRubric, setPolicyRubric] = useState(
    "Check whether the answer is supported by the provided context. Pass only grounded answers.",
  );
  const [policyRubricVersion, setPolicyRubricVersion] =
    useState("grounding-v1");
  const [importOpen, setImportOpen] = useState(false),
    [importName, setImportName] = useState(""),
    [importVersion, setImportVersion] = useState("1"),
    [importContent, setImportContent] = useState(""),
    [importFormat, setImportFormat] = useState("json"),
    [importKind, setImportKind] = useState("dataset");
  const [result, setResult] = useState<Result | null>(null),
    [reviewComment, setReviewComment] = useState(""),
    [reviewVerdict, setReviewVerdict] = useState("pass"),
    [approveOpen, setApproveOpen] = useState(false),
    [approveComment, setApproveComment] = useState("");
  const [filter, setFilter] = useState("all");
  const modalError = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Action errors must be visible even after submitting a long mobile form.
    // Background polling never sets error, so refreshes do not move keyboard focus.
    if (error && modalError.current) {
      modalError.current.focus({ preventScroll: true });
      modalError.current.scrollIntoView({ block: "nearest" });
    }
  }, [error]);
  const operator = user?.role === "operator" || user?.role === "admin",
    reviewer = user?.role === "reviewer" || user?.role === "admin";
  const refresh = useCallback(async () => {
    const [ds, cs, js] = await Promise.all([
      api<Dataset[]>("/datasets"),
      api<Configuration[]>("/configurations"),
      api<Job[]>("/jobs"),
    ]);
    setDatasets(ds);
    setConfigs(cs);
    setJobs(js);
    setDatasetId((current) => current || ds[0]?.id || "");
    setConfigId(
      (current) =>
        current || cs.find((c) => !c.require_llm)?.id || cs[0]?.id || "",
    );
  }, []);
  useEffect(() => {
    let active = true;
    Promise.allSettled([
      api<ModeStatus>("/status"),
      api<User>("/auth/me"),
    ]).then(async ([s, u]) => {
      if (!active) return;
      if (s.status === "fulfilled" && ["DEMO", "LIVE"].includes(s.value.mode)) {
        setStatus(s.value);
        setPassword(s.value.mode === "DEMO" ? "demo-release" : "");
      } else {
        setError(
          "Workspace mode could not be confirmed. Retry before signing in.",
        );
      }
      if (u.status === "fulfilled") {
        setUser(u.value);
        try {
          await refresh();
        } catch (e) {
          setError((e as Error).message);
        }
      }
      setBooting(false);
    });
    return () => {
      active = false;
    };
  }, [refresh]);
  useEffect(() => {
    if (!user) return;
    const timer = setInterval(async () => {
      try {
        const all = await api<Job[]>("/jobs");
        setJobs(all);
        if (
          job &&
          ["queued", "running", "cancel_requested"].includes(job.status)
        )
          setJob(await api<Job>(`/jobs/${job.id}`));
      } catch {
        /* Visible actions report failures; a transient background refresh keeps the last results. */
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [user, job]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function login(e: React.FormEvent) {
    e.preventDefault();
    if (!status || !["DEMO", "LIVE"].includes(status.mode)) return;
    await action(async () => {
      setUser(
        await api<User>("/auth/login", {
          username: status.mode === "DEMO" ? loginRole : username,
          password,
        }),
      );
      await refresh();
    });
  }
  async function retryStatus() {
    await action(async () => {
      const next = await api<ModeStatus>("/status");
      if (!["DEMO", "LIVE"].includes(next.mode)) {
        throw new Error("Workspace mode could not be confirmed. Please retry.");
      }
      setStatus(next);
      setPassword(next.mode === "DEMO" ? "demo-release" : "");
    });
  }
  async function openJob(id: string) {
    await action(async () => {
      setJob(await api<Job>(`/jobs/${id}`));
      setResult(null);
    });
  }
  async function createRun(e: React.FormEvent) {
    e.preventDefault();
    await action(async () => {
      const created = await api<Job>("/jobs", {
        dataset_id: datasetId,
        configuration_id: configId,
        fixture,
        label,
        source: status?.mode === "LIVE" ? runSource : "fixture",
        ...(status?.mode === "LIVE" && runSource === "endpoint"
          ? { endpoint_id: endpointId }
          : {}),
      });
      setCreateOpen(false);
      await refresh();
      setJob(created);
      setNotice(
        status?.mode === "LIVE"
          ? "LIVE evaluation queued. Provider errors will be reported without a demo fallback."
          : "Evaluation queued. Results are calculated from the selected fixture outputs.",
      );
    });
  }
  async function compare(e: React.FormEvent) {
    e.preventDefault();
    await action(async () => {
      setComparison(
        await api<Comparison>(
          `/compare?baseline=${encodeURIComponent(baseline)}&candidate=${encodeURIComponent(candidate)}`,
        ),
      );
    });
  }
  async function importData(e: React.FormEvent) {
    e.preventDefault();
    await action(async () => {
      if (importKind === "dataset") {
        await api("/datasets/import", {
          name: importName,
          version: importVersion,
          format: importFormat,
          content: importContent,
        });
        setNotice("Dataset validated and saved as a new version.");
      } else {
        const created = await api<Job>("/jobs/import", {
          dataset_id: datasetId,
          configuration_id: configId,
          label: importName,
          format: importFormat,
          content: importContent,
        });
        setJob(created);
        setNotice("Outputs imported. Evaluation queued.");
      }
      setImportOpen(false);
      setImportContent("");
      await refresh();
    });
  }
  async function review(e: React.FormEvent) {
    e.preventDefault();
    if (!job || !result) return;
    await action(async () => {
      await api(`/jobs/${job.id}/review`, {
        case_id: result.case_id,
        verdict: reviewVerdict,
        comment: reviewComment,
      });
      setJob(await api<Job>(`/jobs/${job.id}`));
      setResult(null);
      setReviewComment("");
      setNotice("Human review recorded with your identity and comment.");
      await refresh();
    });
  }
  const completed = jobs.filter((j) => j.status === "completed"),
    rejected = jobs.filter((j) => j.decision === "rejected"),
    pending = jobs.filter((j) => j.decision === "inconclusive");
  const activeJobs = jobs.filter((j) =>
    ["queued", "running"].includes(j.status),
  );
  const displayedJobs = jobs.filter(
    (j) => filter === "all" || j.decision === filter,
  );
  const closeOverlay = () => {
    setJob(null);
    setDataset(null);
    setCreateOpen(false);
    setImportOpen(false);
    setConfigOpen(false);
    setResult(null);
    setApproveOpen(false);
  };
  useEffect(() => {
    function escape(e: KeyboardEvent) {
      if (e.key === "Escape") closeOverlay();
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, []);
  const dialogOpen = Boolean(
    createOpen || importOpen || configOpen || job || dataset,
  );
  useEffect(() => {
    if (!dialogOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialogs = document.querySelectorAll<HTMLElement>("[role=dialog]");
    const dialog = dialogs[dialogs.length - 1];
    const selector =
      'button:not(:disabled), a[href], input, select, textarea, summary, [tabindex="0"]';
    const nodes = () =>
      Array.from(dialog?.querySelectorAll<HTMLElement>(selector) || []).filter(
        (el) => el.offsetParent !== null,
      );
    nodes()[0]?.focus();
    function trap(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const list = nodes(),
        first = list[0],
        last = list[list.length - 1];
      if (!first) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [dialogOpen, result?.case_id]);
  const mode = status?.mode || "UNKNOWN";
  if (booting)
    return (
      <div className="boot">
        <Brand />
        <span className="spinner" />
        <p>Opening your workspace…</p>
      </div>
    );
  if (!user || mode === "UNKNOWN")
    return (
      <main className="login-page">
        <section className="login-story">
          <Brand />
          <div>
            <h1>
              Better releases
              <br />
              start with
              <br />
              <em>better questions.</em>
            </h1>
            <p>
              A decision workspace for generative AI. Inspect the evidence,
              catch regressions, and know when to hold a release.
            </p>
            <div className="login-trust">
              <Icon name="shield" />
              Traceable decisions. Explicit uncertainty.
            </div>
          </div>
          <span className="login-foot">
            Fictional organization · original synthetic data
          </span>
        </section>
        <section className="login-form-area">
          <div className="login-form">
            <div className="mode-line">
              <span className="mode-badge">{mode} MODE</span>
              <span>
                {mode === "DEMO"
                  ? "No API key needed"
                  : mode === "UNKNOWN"
                    ? "Connection verification needed"
                    : status?.live.ready
                      ? "Provider configured"
                      : "Provider configuration needed"}
              </span>
            </div>
            <h2>Your release workspace</h2>
            <p className="muted">
              {mode === "DEMO"
                ? "Choose a demo role to explore the full evaluation workflow."
                : mode === "LIVE"
                  ? "Sign in with your provisioned workspace account."
                  : "The workspace mode must be verified before you sign in."}
            </p>
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            {mode === "UNKNOWN" ? (
              <button
                className="button primary full"
                disabled={busy}
                onClick={retryStatus}
              >
                {busy ? "Checking connection…" : "Retry connection"}
              </button>
            ) : (
              <form onSubmit={login}>
                {mode === "DEMO" ? (
                  <>
                    <label htmlFor="role">Workspace role</label>
                    <select
                      id="role"
                      value={loginRole}
                      onChange={(e) => setLoginRole(e.target.value)}
                    >
                      <option value="operator">
                        Operator · datasets and evaluations
                      </option>
                      <option value="reviewer">
                        Reviewer · corrections and approvals
                      </option>
                      <option value="viewer">Viewer · read-only access</option>
                    </select>
                  </>
                ) : (
                  <>
                    <label htmlFor="username">Username</label>
                    <input
                      id="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      autoComplete="username"
                      required
                    />
                  </>
                )}
                <label htmlFor="password">
                  {mode === "DEMO" ? "Demo password" : "Password"}
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                {mode === "DEMO" && (
                  <p className="field-hint">
                    Shared demo password: <code>demo-release</code>
                  </p>
                )}
                <button className="button primary full" disabled={busy}>
                  {busy ? "Opening workspace…" : "Enter workspace"}
                  <Icon name="arrow" />
                </button>
              </form>
            )}
            <div className="login-note">
              <Icon name="info" />
              <p>
                {mode === "DEMO"
                  ? "Demo outputs are labeled fixtures. The database, evaluations, permissions, and release rules execute for real."
                  : mode === "LIVE"
                    ? "LIVE requests use configured providers or registered endpoints. Imported outputs retain their provenance; provider failures never use demo fixtures."
                    : "No credentials are requested until the server confirms its mode."}
              </p>
            </div>
          </div>
        </section>
      </main>
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">
          <span className="workspace-avatar">N</span>
          <span>
            Northstar Sandbox<small>Evaluation workspace</small>
          </span>
        </div>
        <div className="nav-label">Workspace</div>
        <nav aria-label="Main navigation">
          <button
            className={tab === "runs" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("runs")}
            aria-current={tab === "runs" ? "page" : undefined}
          >
            <Icon name="grid" />
            Evaluation runs<span className="nav-count">{jobs.length}</span>
          </button>
          <button
            className={tab === "datasets" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("datasets")}
            aria-current={tab === "datasets" ? "page" : undefined}
          >
            <Icon name="stack" />
            Dataset library
          </button>
          <button
            className={tab === "compare" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("compare")}
            aria-current={tab === "compare" ? "page" : undefined}
          >
            <Icon name="compare" />
            Compare versions
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="profile">
            <div className="avatar">{user.username[0].toUpperCase()}</div>
            <div>
              <strong>{user.username}</strong>
              <small>{user.role}</small>
            </div>
            <button
              className="icon-button"
              title="Sign out"
              aria-label="Sign out"
              onClick={() =>
                action(async () => {
                  await api("/auth/logout", {});
                  setUser(null);
                  setJob(null);
                  setTab("runs");
                })
              }
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span className="breadcrumbs">
            Workspace <span>/</span>{" "}
            {tab === "runs"
              ? "Evaluation runs"
              : tab === "datasets"
                ? "Dataset library"
                : "Compare versions"}
          </span>
          <div className="mode-line">
            <span className="synthetic-tag">Synthetic data</span>
            <span className="mode-badge">{mode} MODE</span>
          </div>
        </header>
        <main id="main" className="main-content">
          <div className="page-heading">
            <div>
              <h1>
                {tab === "runs"
                  ? "Evaluation runs"
                  : tab === "datasets"
                    ? "Datasets and release policies"
                    : "Compare versions"}
              </h1>
              <p>
                {tab === "runs"
                  ? "Each run checks one version against a versioned dataset and release policy. Release approval needs every mandatory check to have a result."
                  : tab === "datasets"
                    ? "Versioned cases with expectations you can inspect and reproduce, and the rules a release must meet."
                    : "Runs are paired on identical case contracts: what improved, what regressed and what is missing."}
              </p>
            </div>
            {operator && (
              <button
                className="button primary"
                onClick={() => {
                  setCreateOpen(true);
                  setError("");
                }}
              >
                <Icon name="plus" size={18} />
                New evaluation
              </button>
            )}
          </div>
          {error && (
            <div className="alert error" role="alert">
              <Icon name="info" />
              {error}
              <button
                aria-label="Dismiss error"
                className="icon-button"
                onClick={() => setError("")}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Icon name="check" />
              {notice}
              <button
                aria-label="Dismiss notification"
                className="icon-button"
                onClick={() => setNotice("")}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          <div className="demo-banner">
            <span className="demo-indicator" />
            <span>
              <strong>
                {mode === "DEMO"
                  ? "A working lab. Clearly labeled fixtures."
                  : "LIVE execution enabled."}
              </strong>{" "}
              {mode === "DEMO"
                ? "Evaluations run against synthetic outputs. These are software checks, not measured model quality."
                : "Provider usage is recorded only when returned. No demo fallback."}
            </span>
            <button
              onClick={() => {
                setTab("datasets");
                setNotice(
                  status?.live.ready
                    ? "LIVE configuration is ready; use the documented API or CLI for live execution."
                    : `LIVE configuration pending: ${status?.live.missing.join(", ") || "provider configuration"}. Imported outputs remain evaluable; LIVE never switches to demo fixtures.`,
                );
              }}
            >
              Mode details <Icon name="arrow" size={16} />
            </button>
          </div>
          {tab === "runs" && (
            <>
              <section className="metric-grid" aria-label="Evaluation overview">
                <div className="metric">
                  <div>
                    <span>Evaluation runs</span>
                  </div>
                  <strong>{jobs.length}</strong>
                  <small>
                    {completed.length} completed
                    {activeJobs.length > 0
                      ? ` · ${activeJobs.length} in progress`
                      : ""}
                  </small>
                </div>
                <div className="metric">
                  <div>
                    <span>Release gates passed</span>
                  </div>
                  <strong>
                    {jobs
                      .filter((j) => j.decision === "approved")
                      .length}
                  </strong>
                  <small>All required checks satisfied</small>
                </div>
                <div className="metric">
                  <div>
                    <span>Regressions caught</span>
                  </div>
                  <strong>{rejected.length}</strong>
                  <small>Runs blocked by release policy</small>
                </div>
                <div className="metric">
                  <div>
                    <span>Needs more evidence</span>
                  </div>
                  <strong>{pending.length}</strong>
                  <small>Inconclusive release decisions</small>
                </div>
              </section>
              <section className="panel runs-panel">
                <div className="section-heading">
                  <div>
                    <h2>
                      All runs{" "}
                      <span className="count-pill">{jobs.length}</span>
                    </h2>
                  </div>
                  <div className="row-actions">
                    {operator && (
                      <button
                        className="button subtle small"
                        onClick={() => {
                          setImportKind("outputs");
                          setImportName("Imported evaluation");
                          setImportOpen(true);
                        }}
                      >
                        <Icon name="download" size={16} />
                        Import outputs
                      </button>
                    )}
                    <label className="sr-only" htmlFor="decision-filter">
                      Filter decisions
                    </label>
                    <select
                      id="decision-filter"
                      className="compact-select"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">All decisions</option>
                      <option value="approved">Approved</option>
                      <option value="rejected">Rejected</option>
                      <option value="inconclusive">Inconclusive</option>
                    </select>
                  </div>
                </div>
                {displayedJobs.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Run / version</th>
                          <th>Execution</th>
                          <th>Checks passed</th>
                          <th>Release gate</th>
                          <th>Created</th>
                          <th>
                            <span className="sr-only">Details</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayedJobs.map((j) => (
                          <tr key={j.id}>
                            <td>
                              <button
                                className="run-name"
                                onClick={() => openJob(j.id)}
                              >
                                {j.label}
                                <small>
                                  <Icon name="file" size={13} />
                                  {shortId(j.id)} <span>·</span> {j.source}{" "}
                                  <span>·</span> {j.mode}
                                </small>
                              </button>
                            </td>
                            <td>
                              <span
                                className={`execution ${j.status === "running" ? "running" : ""}`}
                              >
                                <span />
                                {humanStatus(j.status)}
                              </span>
                            </td>
                            <td>
                              <div className="pass-rate">
                                {percentage(j.summary?.pass_rate)}
                                <small>
                                  {j.summary?.passed ?? 0} /{" "}
                                  {j.summary?.total ?? j.total} cases
                                </small>
                              </div>
                            </td>
                            <td>
                              <Badge value={j.decision || "pending"} />
                            </td>
                            <td className="muted date-cell">
                              {new Date(j.created_at).toLocaleDateString(
                                "en-GB",
                                { day: "2-digit", month: "short" },
                              )}
                              <small>
                                {new Date(j.created_at).toLocaleTimeString(
                                  "en-GB",
                                  { hour: "2-digit", minute: "2-digit" },
                                )}
                              </small>
                            </td>
                            <td>
                              <button
                                className="icon-button"
                                aria-label={`Open ${j.label}`}
                                onClick={() => openJob(j.id)}
                              >
                                <Icon name="chevron" size={18} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty
                    title={
                      filter === "all"
                        ? "Your first release starts here."
                        : "No runs match this decision."
                    }
                  >
                    {filter === "all"
                      ? "Create a reference evaluation, then run the deliberate regression fixture to see the release gate respond."
                      : "Choose a different decision filter."}
                  </Empty>
                )}
                <div className="table-footer">
                  <span>
                    <span className="live-dot" />
                    Persisted results · refreshes automatically
                  </span>
                  <span>
                    {displayedJobs.length}{" "}
                    {displayedJobs.length === 1 ? "run" : "runs"} shown
                  </span>
                </div>
              </section>
              <div className="bottom-grid">
                <section className="policy-card">
                  <div className="section-heading">
                    <h3>What the release gate checks</h3>
                  </div>
                  <div className="policy-row">
                    <span>Deterministic checks</span>
                    <strong>Format, references, tools</strong>
                  </div>
                  <div className="policy-row">
                    <span>Authorization evidence</span>
                    <strong>When trace is sufficient</strong>
                  </div>
                  <div className="policy-row">
                    <span>Required LLM evaluation</span>
                    <strong>Pending blocks approval</strong>
                  </div>
                  <p>
                    Fixture results demonstrate release logic. They are not a
                    guarantee of model safety.
                  </p>
                </section>
              </div>
            </>
          )}
          {tab === "datasets" && (
            <>
              <div className="section-heading standalone">
                <div>
                  <h2>Versioned datasets</h2>
                  <p>Development and final evaluation splits remain visible.</p>
                </div>
                {operator && (
                  <button
                    className="button secondary"
                    onClick={() => {
                      setImportKind("dataset");
                      setImportName("");
                      setImportOpen(true);
                    }}
                  >
                    <Icon name="plus" size={18} />
                    Import dataset
                  </button>
                )}
              </div>
              <div className="dataset-grid">
                {datasets.map((ds) => (
                  <button
                    className="dataset-card"
                    key={ds.id}
                    onClick={() =>
                      action(async () =>
                        setDataset(await api<Dataset>(`/datasets/${ds.id}`)),
                      )
                    }
                  >
                    <div className="dataset-card-top">
                      <span className="dataset-icon">
                        <Icon name="stack" size={25} />
                      </span>
                      <span className="version-label">v{ds.version}</span>
                    </div>
                    <h3>{ds.name}</h3>
                    <p>Original synthetic RAG and agent evaluation cases</p>
                    <div className="dataset-count">
                      <strong>{ds.case_count}</strong>
                      <span>cases</span>
                    </div>
                    <div className="split-bar">
                      <i
                        style={{
                          width: `${((ds.split_counts.development || 0) / Math.max(ds.case_count, 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <div className="split-labels">
                      <span>
                        <i />
                        Development <b>{ds.split_counts.development || 0}</b>
                      </span>
                      <span>
                        <i />
                        Final <b>{ds.split_counts.final || 0}</b>
                      </span>
                    </div>
                    <div className="dataset-foot">
                      <code>{ds.hash.slice(0, 12)}</code>
                      <span>
                        Inspect cases <Icon name="arrow" size={16} />
                      </span>
                    </div>
                  </button>
                ))}
              </div>
              <div className="panel config-panel">
                <div className="section-heading">
                  <div>
                    <h2>Release policies</h2>
                    <p>Versioned configurations are recorded with every run.</p>
                  </div>
                  {operator && (
                    <button
                      className="button secondary small"
                      onClick={() => {
                        setConfigOpen(true);
                        setError("");
                      }}
                    >
                      <Icon name="plus" size={16} />
                      New policy version
                    </button>
                  )}
                </div>
                {configs.map((c) => (
                  <div className="config-row" key={c.id}>
                    <Icon name="shield" />
                    <div>
                      <strong>{c.name}</strong>
                      <small>
                        Version {c.version} · {c.hash.slice(0, 12)}
                      </small>
                    </div>
                    <span>Threshold {percentage(c.threshold)}</span>
                    <span
                      className={`badge ${c.require_llm ? "amber" : "neutral"}`}
                    >
                      {c.require_llm
                        ? "LLM review required"
                        : "Deterministic checks"}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
          {tab === "compare" && (
            <>
              <section className="panel compare-panel">
                <div className="section-heading">
                  <div>
                    <h2>Compare evaluation runs</h2>
                    <p>
                      Choose a reference and a candidate. Cases are paired only
                      when their IDs and full case content match.
                    </p>
                  </div>
                  <Icon name="compare" size={26} />
                </div>
                <form className="compare-form" onSubmit={compare}>
                  <div>
                    <label htmlFor="baseline">Baseline run</label>
                    <select
                      id="baseline"
                      value={baseline}
                      onChange={(e) => setBaseline(e.target.value)}
                      required
                    >
                      <option value="">Select a baseline</option>
                      {completed.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.label} · {shortId(j.id)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="compare-arrow">
                    <Icon name="arrow" />
                  </div>
                  <div>
                    <label htmlFor="candidate">Candidate run</label>
                    <select
                      id="candidate"
                      value={candidate}
                      onChange={(e) => setCandidate(e.target.value)}
                      required
                    >
                      <option value="">Select a candidate</option>
                      {completed
                        .filter((j) => j.id !== baseline)
                        .map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.label} · {shortId(j.id)}
                          </option>
                        ))}
                    </select>
                  </div>
                  <button
                    className="button primary"
                    disabled={busy || !baseline || !candidate}
                  >
                    Compare runs
                    <Icon name="compare" size={18} />
                  </button>
                </form>
              </section>
              {comparison ? (
                <>
                  <div className="metric-grid compare-metrics">
                    <div className="metric">
                      <div>
                        <span>Paired cases</span>
                        <Icon name="compare" />
                      </div>
                      <strong>{comparison.paired}</strong>
                      <small>
                        {comparison.total_baseline} baseline /{" "}
                        {comparison.total_candidate} candidate
                      </small>
                    </div>
                    <div className="metric">
                      <div>
                        <span>Regressions</span>
                        <span className="mini-dot red" />
                      </div>
                      <strong>{comparison.regressions.length}</strong>
                      <small>Passed baseline → failed candidate</small>
                    </div>
                    <div className="metric">
                      <div>
                        <span>Pass rate change</span>
                        <span className="mini-dot amber" />
                      </div>
                      <strong>
                        {comparison.delta_pass_rate === null
                          ? "Pending"
                          : `${comparison.delta_pass_rate > 0 ? "+" : ""}${Math.round(comparison.delta_pass_rate * 100)} pp`}
                      </strong>
                      <small>
                        {comparison.pending_pairs
                          ? `${comparison.pending_pairs} pairs lack completed evidence`
                          : "Percentage point difference"}
                      </small>
                    </div>
                    <div className="metric">
                      <div>
                        <span>Unpaired cases</span>
                        <Icon name="info" />
                      </div>
                      <strong>
                        {comparison.missing_baseline.length +
                          comparison.missing_candidate.length +
                          comparison.incompatible_cases.length}
                      </strong>
                      <small>
                        {comparison.improvements.length} paired improvements
                      </small>
                    </div>
                  </div>
                  {(comparison.incompatible_cases.length > 0 ||
                    comparison.unprocessed_baseline.length > 0 ||
                    comparison.unprocessed_candidate.length > 0 ||
                    !comparison.same_evaluator ||
                    !comparison.same_configuration) && (
                    <section
                      className="panel missing-panel"
                      aria-label="Comparison limitations"
                    >
                      <h3>Comparison limitations</h3>
                      <p>
                        Changed case contracts excluded:{" "}
                        {comparison.incompatible_cases.join(", ") || "None"}
                      </p>
                      <p>
                        Not yet evaluated in baseline:{" "}
                        {comparison.unprocessed_baseline.join(", ") || "None"}
                      </p>
                      <p>
                        Not yet evaluated in candidate:{" "}
                        {comparison.unprocessed_candidate.join(", ") || "None"}
                      </p>
                      {!comparison.same_evaluator && (
                        <p>
                          Evaluator versions differ. Interpret this comparison
                          as exploratory.
                        </p>
                      )}
                      {!comparison.same_configuration && (
                        <p>
                          Evaluation configurations differ. Inspect their
                          versioned rules before interpreting changes.
                        </p>
                      )}
                    </section>
                  )}
                  <section className="panel">
                    <div className="section-heading">
                      <div>
                        <h2>Regressions to investigate</h2>
                        <p>
                          Inspect the candidate run for individual check details
                          and human review.
                        </p>
                      </div>
                      <button
                        className="button secondary small"
                        onClick={() => openJob(candidate)}
                      >
                        Open candidate
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                    {comparison.regressions.length ? (
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Case</th>
                              <th>Baseline</th>
                              <th>Candidate</th>
                              <th>Change</th>
                            </tr>
                          </thead>
                          <tbody>
                            {comparison.regressions.map((r) => (
                              <tr key={r.case_id}>
                                <td>
                                  <code>{r.case_id}</code>
                                </td>
                                <td>
                                  <Badge
                                    value={
                                      typeof r.baseline === "string"
                                        ? r.baseline
                                        : "pass"
                                    }
                                  />
                                </td>
                                <td>
                                  <Badge
                                    value={
                                      typeof r.candidate === "string"
                                        ? r.candidate
                                        : "fail"
                                    }
                                  />
                                </td>
                                <td className="regression-label">
                                  Regression detected
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <Empty title="No paired regressions found.">
                        Review missing cases and pending checks before
                        interpreting this result.
                      </Empty>
                    )}
                  </section>
                  {(comparison.missing_baseline.length > 0 ||
                    comparison.missing_candidate.length > 0) && (
                    <section className="panel missing-panel">
                      <h3>Missing cases are not counted as passes</h3>
                      <p>
                        Missing baseline:{" "}
                        {comparison.missing_baseline.join(", ") || "None"}
                      </p>
                      <p>
                        Missing candidate:{" "}
                        {comparison.missing_candidate.join(", ") || "None"}
                      </p>
                    </section>
                  )}
                </>
              ) : (
                <Empty title="See the change behind the score.">
                  Create a reference and regression evaluation, then compare
                  their case-level results here.
                </Empty>
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>GenAI Release Lab</span>
            <span>
              Original synthetic data · No regulatory compliance claim
            </span>
            <a href="/api/docs" target="_blank" rel="noreferrer">
              API reference ↗
            </a>
          </footer>
        </main>
      </div>
      {(createOpen || importOpen || configOpen || job || dataset) && (
        <div
          className="overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeOverlay();
          }}
        >
          <section
            className={`drawer ${job ? "wide-drawer" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-label={
              createOpen
                ? "New evaluation"
                : importOpen
                  ? "Import data"
                  : configOpen
                    ? "New release policy"
                    : dataset
                      ? "Dataset details"
                      : "Evaluation details"
            }
          >
            <button
              className="drawer-close icon-button"
              aria-label="Close dialog"
              onClick={closeOverlay}
            >
              <Icon name="close" />
            </button>
            {error && (
              <div
                className="alert error"
                role="alert"
                ref={modalError}
                tabIndex={-1}
              >
                {error}
              </div>
            )}
            {createOpen && (
              <>
                <h2>New evaluation</h2>
                <p className="muted">
                  {mode === "LIVE"
                    ? "Execute the configured model API or an endpoint registered by an authorized operator."
                    : "Fixture outputs are evaluated by the same release rules as imported or LIVE outputs."}
                </p>
                <form onSubmit={createRun} className="stack-form">
                  <label htmlFor="run-label">Run label</label>
                  <input
                    id="run-label"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    required
                    maxLength={100}
                  />
                  <label htmlFor="run-dataset">Dataset version</label>
                  <select
                    id="run-dataset"
                    value={datasetId}
                    onChange={(e) => setDatasetId(e.target.value)}
                  >
                    {datasets.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} · v{d.version} · {d.case_count} cases
                      </option>
                    ))}
                  </select>
                  <label htmlFor="run-policy">Release policy</label>
                  <select
                    id="run-policy"
                    value={configId}
                    onChange={(e) => setConfigId(e.target.value)}
                  >
                    {configs.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                        {c.require_llm ? " · LLM required" : ""}
                      </option>
                    ))}
                  </select>
                  {mode === "DEMO" ? (
                    <>
                      <label htmlFor="run-fixture">Fixture output set</label>
                      <select
                        id="run-fixture"
                        value={fixture}
                        onChange={(e) => {
                          setFixture(e.target.value);
                          setLabel(
                            e.target.value === "reference"
                              ? "Reference evaluation"
                              : "Regression evaluation",
                          );
                        }}
                      >
                        <option value="reference">
                          Reference · expected behavior
                        </option>
                        <option value="regression">
                          Regression · deliberate failures
                        </option>
                      </select>
                    </>
                  ) : (
                    <>
                      <label htmlFor="run-source">Execution source</label>
                      <select
                        id="run-source"
                        value={runSource}
                        onChange={(e) => setRunSource(e.target.value)}
                      >
                        <option value="api">Configured model API</option>
                        <option value="endpoint">Registered endpoint</option>
                      </select>
                      {runSource === "endpoint" && (
                        <>
                          <label htmlFor="run-endpoint">
                            Registered endpoint ID
                          </label>
                          <input
                            id="run-endpoint"
                            value={endpointId}
                            onChange={(e) => setEndpointId(e.target.value)}
                            required
                          />
                          <p className="field-hint">
                            An operator must register the allowed destination
                            through the API before running it.
                          </p>
                        </>
                      )}
                    </>
                  )}
                  <div className="inline-note">
                    <Icon name="info" />
                    <p>
                      {mode === "DEMO"
                        ? "No model call is made for fixture runs. Selecting an LLM-required policy can leave the gate inconclusive until that evaluation is available."
                        : status?.live.ready
                          ? "LIVE requests may incur provider charges. Check the selected configuration before starting."
                          : `LIVE configuration is incomplete: ${status?.live.missing.join(", ")}. Model execution needs credentials for the selected configuration. Authorized endpoint execution is checked separately.`}
                    </p>
                  </div>
                  <button
                    className="button primary full"
                    disabled={busy || !datasetId || !configId}
                  >
                    <Icon name="play" size={17} />
                    {busy ? "Queuing evaluation…" : "Start evaluation"}
                  </button>
                </form>
              </>
            )}
            {configOpen && (
              <>
                <h2>New release policy version</h2>
                <p className="muted">
                  Create an immutable policy version. Each evaluation records
                  its exact configuration and hash.
                </p>
                <form
                  className="stack-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    action(async () => {
                      const created = await api<Configuration>(
                        "/configurations",
                        {
                          name: policyName,
                          version: policyVersion,
                          threshold: Number(policyThreshold) / 100,
                          require_llm: policyLlm,
                          rubric: policyRubric,
                          rubric_version: policyRubricVersion,
                          provider: policyProvider,
                          model: policyModel,
                        },
                      );
                      await refresh();
                      setConfigId(created.id);
                      setConfigOpen(false);
                      setNotice(
                        "Release policy version created and selected for the next evaluation.",
                      );
                    });
                  }}
                >
                  <label htmlFor="policy-name">Policy name</label>
                  <input
                    id="policy-name"
                    value={policyName}
                    onChange={(e) => setPolicyName(e.target.value)}
                    required
                    maxLength={100}
                  />
                  <label htmlFor="policy-version">Policy version</label>
                  <input
                    id="policy-version"
                    value={policyVersion}
                    onChange={(e) => setPolicyVersion(e.target.value)}
                    required
                    maxLength={40}
                  />
                  <label htmlFor="policy-threshold">
                    Required case pass rate (%)
                  </label>
                  <input
                    id="policy-threshold"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={policyThreshold}
                    onChange={(e) => setPolicyThreshold(e.target.value)}
                    required
                  />
                  <label htmlFor="policy-llm">Required evaluation</label>
                  <select
                    id="policy-llm"
                    value={policyLlm ? "llm" : "deterministic"}
                    onChange={(e) => setPolicyLlm(e.target.value === "llm")}
                  >
                    <option value="deterministic">Deterministic checks</option>
                    <option value="llm">
                      Deterministic checks + mandatory LLM review
                    </option>
                  </select>
                  <label htmlFor="policy-provider">Model API provider</label>
                  <select
                    id="policy-provider"
                    value={policyProvider}
                    onChange={(e) => {
                      setPolicyProvider(e.target.value);
                      setPolicyModel(
                        e.target.value === "openai"
                          ? "gpt-4.1-mini"
                          : "gemini-2.5-flash",
                      );
                    }}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                  </select>
                  <label htmlFor="policy-model">Model identifier</label>
                  <input
                    id="policy-model"
                    value={policyModel}
                    onChange={(e) => setPolicyModel(e.target.value)}
                    required
                    maxLength={100}
                  />
                  {policyLlm && (
                    <>
                      <label htmlFor="policy-rubric-version">
                        Rubric version
                      </label>
                      <input
                        id="policy-rubric-version"
                        value={policyRubricVersion}
                        onChange={(e) => setPolicyRubricVersion(e.target.value)}
                        required
                      />
                      <label htmlFor="policy-rubric">Evaluation rubric</label>
                      <textarea
                        id="policy-rubric"
                        value={policyRubric}
                        onChange={(e) => setPolicyRubric(e.target.value)}
                        rows={4}
                        required
                        maxLength={5000}
                      />
                    </>
                  )}
                  <div className="inline-note">
                    <Icon name="info" />
                    <p>
                      A missing mandatory evaluation makes the release
                      inconclusive, regardless of the pass-rate threshold.
                      Creating this policy makes no model calls.
                    </p>
                  </div>
                  <button className="button primary full" disabled={busy}>
                    Create policy version
                  </button>
                </form>
              </>
            )}
            {importOpen && (
              <>
                <div className="eyebrow">Validated import</div>
                <h2>
                  {importKind === "dataset"
                    ? "Add a dataset version."
                    : "Evaluate your own outputs."}
                </h2>
                <p className="muted">
                  Paste JSON or JSONL. Invalid records are rejected with an
                  explanation.
                </p>
                <form className="stack-form" onSubmit={importData}>
                  <label htmlFor="import-name">
                    {importKind === "dataset" ? "Dataset name" : "Run label"}
                  </label>
                  <input
                    id="import-name"
                    value={importName}
                    onChange={(e) => setImportName(e.target.value)}
                    required
                  />
                  {importKind === "dataset" ? (
                    <>
                      <label htmlFor="import-version">Version</label>
                      <input
                        id="import-version"
                        value={importVersion}
                        onChange={(e) => setImportVersion(e.target.value)}
                        required
                      />
                    </>
                  ) : (
                    <>
                      <label htmlFor="import-dataset">Dataset</label>
                      <select
                        id="import-dataset"
                        value={datasetId}
                        onChange={(e) => setDatasetId(e.target.value)}
                      >
                        {datasets.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name} v{d.version}
                          </option>
                        ))}
                      </select>
                      <label htmlFor="import-config">Policy</label>
                      <select
                        id="import-config"
                        value={configId}
                        onChange={(e) => setConfigId(e.target.value)}
                      >
                        {configs.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </>
                  )}
                  <label htmlFor="import-format">Format</label>
                  <select
                    id="import-format"
                    value={importFormat}
                    onChange={(e) => setImportFormat(e.target.value)}
                  >
                    <option value="json">JSON array</option>
                    <option value="jsonl">JSONL · one object per line</option>
                  </select>
                  <label htmlFor="import-content">
                    {importKind === "dataset"
                      ? "Case records"
                      : "Output records"}
                  </label>
                  <textarea
                    id="import-content"
                    rows={10}
                    value={importContent}
                    onChange={(e) => setImportContent(e.target.value)}
                    required
                    placeholder={
                      importKind === "dataset"
                        ? "Use the case schema in the API reference."
                        : '[{"case_id":"…","output":{"answer":"…","citations":[],"tool_calls":[],"authorization":{}}}]'
                    }
                  />
                  <p className="field-hint">
                    For the full schema, see the{" "}
                    <a href="/api/docs" target="_blank" rel="noreferrer">
                      API reference
                    </a>
                    . Imports are stored as provenance, not model performance
                    claims.
                  </p>
                  <button className="button primary full" disabled={busy}>
                    {busy ? "Validating…" : "Validate and import"}
                  </button>
                </form>
              </>
            )}
            {dataset && (
              <>
                <div className="eyebrow">Dataset version {dataset.version}</div>
                <h2>{dataset.name}</h2>
                <p className="muted">
                  {dataset.case_count} cases · immutable content hash
                </p>
                <code className="hash-block">{dataset.hash}</code>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Case</th>
                        <th>Split</th>
                        <th>Prompt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataset.cases?.map((c, i) => (
                        <tr key={c.case_id || c.id || i}>
                          <td>
                            <code>{c.case_id || c.id}</code>
                          </td>
                          <td>
                            <span className="badge neutral">{c.split}</span>
                          </td>
                          <td>{c.prompt || JSON.stringify(c).slice(0, 130)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            {job && (
              <>
                <div className="eyebrow">Evaluation · {shortId(job.id)}</div>
                <div className="job-title">
                  <h2>{job.label}</h2>
                  <Badge value={job.decision || "pending"} />
                </div>
                <p className="muted">
                  {job.source} source · {job.mode} · {humanStatus(job.status)}
                </p>
                <div className="job-progress">
                  <span
                    style={{
                      width: `${job.total ? (job.progress / job.total) * 100 : 0}%`,
                    }}
                  />
                </div>
                <p className="field-hint">
                  {job.progress} / {job.total} cases processed
                </p>
                {job.error && <div className="alert error">{job.error}</div>}
                <div className="job-stats">
                  <div>
                    <strong>{job.summary?.passed ?? 0}</strong>
                    <span>Passed</span>
                  </div>
                  <div>
                    <strong>{job.summary?.failed ?? 0}</strong>
                    <span>Failed</span>
                  </div>
                  <div>
                    <strong>{job.summary?.pending ?? 0}</strong>
                    <span>Pending</span>
                  </div>
                  <div>
                    <strong>{percentage(job.summary?.pass_rate)}</strong>
                    <span>Pass rate</span>
                  </div>
                </div>
                <div className="job-actions">
                  <div className="export-actions">
                    <span>Export</span>
                    {["json", "junit", "html"].map((f) => (
                      <a
                        key={f}
                        className="button secondary small"
                        href={`/api/jobs/${job.id}/export?format=${f}`}
                        download
                      >
                        <Icon name="download" size={14} />
                        {f.toUpperCase()}
                      </a>
                    ))}
                  </div>
                  {operator && ["queued", "running"].includes(job.status) && (
                    <button
                      className="button danger small"
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          await api(`/jobs/${job.id}/cancel`, {});
                          setJob(await api<Job>(`/jobs/${job.id}`));
                          setNotice(
                            "Cancellation requested. Completed case results remain available.",
                          );
                        })
                      }
                    >
                      Cancel run
                    </button>
                  )}
                  {reviewer &&
                    job.decision === "approved" &&
                    !job.approvals?.length && (
                      <button
                        className="button primary small"
                        onClick={() => setApproveOpen(true)}
                      >
                        <Icon name="shield" size={16} />
                        Record approval
                      </button>
                    )}
                </div>
                {(() => {
                  const signoff = releaseSignoff(job);
                  return (
                    <div
                      className={`inline-note signoff signoff-${signoff.tone}`}
                      role="note"
                      aria-label="Release sign-off"
                    >
                      <Icon name="shield" />
                      <p>{signoff.text}</p>
                    </div>
                  );
                })()}
                {!!job.reviews?.length && (
                  <div className="inline-note" aria-label="Human corrections">
                    <Icon name="check" />
                    <p>
                      Human corrections ({job.reviews.length}), append-only;
                      automated evidence is preserved:{" "}
                      {job.reviews
                        .map(
                          (r) =>
                            `${r.case_id} → ${r.verdict} by ${r.actor} (“${r.comment}”)`,
                        )
                        .join(" · ")}
                    </p>
                  </div>
                )}
                {approveOpen && (
                  <form
                    className="review-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      action(async () => {
                        await api(`/jobs/${job.id}/approve`, {
                          comment: approveComment,
                        });
                        setApproveOpen(false);
                        setNotice("Release approval recorded.");
                        setJob(await api<Job>(`/jobs/${job.id}`));
                      });
                    }}
                  >
                    <h3>Confirm release approval</h3>
                    <p>
                      This records your approval of this evaluated run and its
                      recorded configuration.
                    </p>
                    <label htmlFor="approval-comment">Approval note</label>
                    <textarea
                      id="approval-comment"
                      value={approveComment}
                      onChange={(e) => setApproveComment(e.target.value)}
                      required
                      minLength={3}
                    />
                    <button className="button primary" disabled={busy}>
                      Confirm approval
                    </button>
                  </form>
                )}
                <div className="section-heading result-heading">
                  <h3>Case-level evidence</h3>
                  <span className="muted">
                    {job.results?.length ?? 0} results
                  </span>
                </div>
                {job.results?.length ? (
                  <div className="table-scroll">
                    <table className="result-table">
                      <thead>
                        <tr>
                          <th>Case</th>
                          <th>Split</th>
                          <th>Checks</th>
                          <th>Result</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {job.results.map((r) => (
                          <tr key={r.case_id}>
                            <td>
                              <button
                                className="case-link"
                                onClick={() => {
                                  setResult(r);
                                  setReviewComment("");
                                }}
                              >
                                {r.case_id}
                              </button>
                              {r.prompt && (
                                <span className="case-prompt-line">{r.prompt}</span>
                              )}
                            </td>
                            <td>
                              <span className="split-tag">{r.split}</span>
                            </td>
                            <td>
                              {(() => {
                                const summary = checkSummary(r.checks);
                                return (
                                  <span className={`check-summary ${summary.tone}`}>
                                    {summary.text}
                                  </span>
                                );
                              })()}
                            </td>
                            <td>
                              <Badge value={r.status} />
                            </td>
                            <td>
                              <button
                                className="icon-button"
                                aria-label={`Inspect ${r.case_id}`}
                                onClick={() => {
                                  setResult(r);
                                  setReviewComment("");
                                }}
                              >
                                <Icon name="chevron" size={16} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty
                    title={
                      ["queued", "running"].includes(job.status)
                        ? "Evaluation in progress."
                        : "No case results available."
                    }
                  >
                    Results appear here as the worker completes each case.
                  </Empty>
                )}
                <details className="provenance">
                  <summary>Run provenance and configuration</summary>
                  <pre>
                    {JSON.stringify(
                      Object.fromEntries(
                        Object.entries(job).filter(
                          ([key]) => !["results", "summary"].includes(key),
                        ),
                      ),
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </>
            )}
          </section>
        </div>
      )}
      {result && job && (
        <div className="overlay result-overlay">
          <section
            className="drawer result-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Case ${result.case_id}`}
          >
            <button
              className="drawer-close icon-button"
              aria-label="Close case details"
              onClick={() => setResult(null)}
            >
              <Icon name="close" />
            </button>
            <div className="eyebrow">Case evidence</div>
            <h2>{result.case_id}</h2>
            <Badge value={result.status} />
            {result.prompt && (
              <div className="case-prompt">
                <span className="eyebrow">Prompt under test</span>
                <p>{result.prompt}</p>
              </div>
            )}
            <div className="check-list">
              {Object.entries(result.checks).map(([name, c]) => (
                <div key={name} className="check-item">
                  <div>
                    <strong>{humanStatus(name)}</strong>
                    <Badge value={c.status} />
                  </div>
                  <p>{c.detail}</p>
                </div>
              ))}
            </div>
            <details open>
              <summary>Output under evaluation</summary>
              <pre>{JSON.stringify(result.output, null, 2)}</pre>
            </details>
            <details open={result.status !== "pass"}>
              <summary>Expected evidence</summary>
              <pre>{JSON.stringify(result.expected, null, 2)}</pre>
            </details>
            {reviewer ? (
              <form className="review-form" onSubmit={review}>
                <h3>Record a human correction</h3>
                <p>
                  Human reviews remain traceable. They do not fabricate missing
                  model evaluations.
                </p>
                <label htmlFor="review-verdict">Verdict</label>
                <select
                  id="review-verdict"
                  value={reviewVerdict}
                  onChange={(e) => setReviewVerdict(e.target.value)}
                >
                  <option value="pass">Pass</option>
                  <option value="fail">Fail</option>
                </select>
                <label htmlFor="review-comment">Reason for correction</label>
                <textarea
                  id="review-comment"
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  required
                  minLength={3}
                />
                <button className="button primary" disabled={busy}>
                  Save human review
                </button>
              </form>
            ) : (
              <div className="inline-note">
                <Icon name="shield" />
                <p>
                  A reviewer can record corrections. Your current role is{" "}
                  {user.role}.
                </p>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
