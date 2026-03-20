"use client";

import { useState } from "react";
import { orchestratorApi, subscriptionApi } from "@/lib/api";
import toast from "react-hot-toast";

interface StepResult {
  step: string;
  status: string;
  message: string;
  data: Record<string, unknown>;
}

interface PipelineResult {
  pipeline_id: string;
  status: string;
  steps: StepResult[];
  total_jobs_found: number;
  total_matched: number;
  total_tailored: number;
  total_applied: number;
}

export default function OrchestratorPage() {
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [maxApps, setMaxApps] = useState(5);
  const [autoTailor, setAutoTailor] = useState(true);
  const [autoApply, setAutoApply] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [hasAccess, setHasAccess] = useState<boolean | null>(null);

  const checkAccess = async () => {
    try {
      const { data } = await subscriptionApi.checkFeature("autonomous_mode");
      setHasAccess(data.allowed);
      return data.allowed;
    } catch {
      setHasAccess(false);
      return false;
    }
  };

  const handleRun = async () => {
    const allowed = await checkAccess();
    if (!allowed) {
      toast.error("Autonomous mode requires Enterprise plan");
      return;
    }

    if (!keywords.trim()) {
      toast.error("Please enter at least one keyword");
      return;
    }

    setRunning(true);
    setResult(null);
    try {
      const { data } = await orchestratorApi.run({
        scrape_keywords: keywords.split(",").map((k: string) => k.trim()).filter(Boolean),
        scrape_location: location || undefined,
        max_applications: maxApps,
        auto_tailor: autoTailor,
        auto_apply: autoApply,
        dry_run: dryRun,
      });
      setResult(data);
      toast.success(dryRun ? "Pipeline plan generated" : "Pipeline completed");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Pipeline failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "success": case "completed": return "text-green-600 dark:text-green-400";
      case "failed": return "text-red-600 dark:text-red-400";
      case "planned": return "text-blue-600 dark:text-blue-400";
      case "running": return "text-yellow-600 dark:text-yellow-400";
      default: return "text-[var(--muted-foreground)]";
    }
  };

  const inputClass =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Autonomous Pipeline</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          One-click job search: scrape, score, tailor resume, and auto-apply.
        </p>
      </div>

      {hasAccess === false && (
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/10 p-4 text-sm text-red-700 dark:text-red-400">
          Autonomous mode requires an <strong>Enterprise</strong> plan. Go to Billing to upgrade.
        </div>
      )}

      {/* Configuration */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 space-y-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Pipeline Configuration</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              Keywords (comma-separated) *
            </label>
            <input
              className={inputClass}
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Software Engineer, Backend, Python"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">Location</label>
            <input
              className={inputClass}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="San Francisco, Remote..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              Max Applications
            </label>
            <input
              className={inputClass}
              type="number"
              min={1}
              max={50}
              value={maxApps}
              onChange={(e) => setMaxApps(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-6 pt-2">
          <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
            <input type="checkbox" checked={autoTailor} onChange={(e) => setAutoTailor(e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
            Auto-tailor resumes
          </label>
          <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
            <input type="checkbox" checked={autoApply} onChange={(e) => setAutoApply(e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
            Auto-apply to jobs
          </label>
          <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
            Dry run (plan only)
          </label>
        </div>

        <button
          onClick={handleRun}
          disabled={running}
          className="rounded-lg bg-purple-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {running ? "Running Pipeline..." : dryRun ? "Generate Plan" : "Launch Pipeline"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Pipeline Result</h3>
            <span className={`text-sm font-medium ${statusColor(result.status)}`}>
              {result.status}
            </span>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Jobs Found", value: result.total_jobs_found },
              { label: "Matched", value: result.total_matched },
              { label: "Tailored", value: result.total_tailored },
              { label: "Applied", value: result.total_applied },
            ].map((stat) => (
              <div key={stat.label} className="rounded-lg bg-[var(--muted)] p-3 text-center">
                <div className="text-2xl font-bold text-[var(--foreground)]">{stat.value}</div>
                <div className="text-xs text-[var(--muted-foreground)]">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Steps */}
          <div className="space-y-2">
            {result.steps.map((step, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-3">
                <span className={`text-lg font-bold ${statusColor(step.status)}`}>
                  {step.status === "success" ? "\u2713" : step.status === "failed" ? "\u2717" : step.status === "planned" ? "\u25CB" : "\u25CF"}
                </span>
                <div className="flex-1">
                  <div className="text-sm font-medium text-[var(--foreground)] capitalize">{step.step}</div>
                  <div className="text-xs text-[var(--muted-foreground)]">{step.message}</div>
                </div>
                <span className={`text-xs font-medium ${statusColor(step.status)}`}>{step.status}</span>
              </div>
            ))}
          </div>

          <p className="text-xs text-[var(--muted-foreground)]">Pipeline ID: {result.pipeline_id}</p>
        </div>
      )}
    </div>
  );
}
