"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  FiCpu,
  FiPlay,
  FiPause,
  FiRefreshCw,
  FiCheckCircle,
  FiAlertCircle,
  FiClock,
  FiActivity,
  FiChevronDown,
  FiChevronUp,
  FiInfo,
} from "react-icons/fi";
import { agentsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";

/* ── Types ─────────────────────────────────────────────────────── */

interface AgentInfo {
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  status: string;
}

interface AgentDashboard {
  agents: Record<string, { enabled: boolean; status: string }>;
  total: number;
  enabled: number;
  running: number;
}

interface Execution {
  id: string;
  agent_name: string;
  status: string;
  items_processed: number;
  duration_seconds: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

/* ── Helpers ───────────────────────────────────────────────────── */

const statusIcon: Record<string, React.ReactNode> = {
  idle: <FiClock className="h-4 w-4 text-gray-400" />,
  running: <FiRefreshCw className="h-4 w-4 text-blue-500 animate-spin" />,
  success: <FiCheckCircle className="h-4 w-4 text-green-500" />,
  failed: <FiAlertCircle className="h-4 w-4 text-red-500" />,
  disabled: <FiPause className="h-4 w-4 text-gray-300" />,
};

const agentLabels: Record<string, string> = {
  job_search: "Job Search",
  recruiter_search: "Recruiter Search",
  resume_tailor: "Resume Tailor",
  application: "Auto Apply",
  web_scraper: "Web Scraper",
  email_checker: "Email Checker",
  recommendations: "Recommendations",
  salary_negotiator: "Salary Negotiator",
  linkedin_message: "LinkedIn Message",
  linkedin_reply: "LinkedIn Reply",
  ats_scorer: "ATS Scorer",
};

const agentTriggerHint: Record<string, string> = {
  job_search: "Uses LinkedIn (authenticated) + Indeed/Naukri. Reads your job preferences from Settings.",
  recruiter_search: "Searches LinkedIn for real recruiters at companies from your saved jobs.",
  resume_tailor: "Requires a saved job. Go to Jobs \u2192 click a job \u2192 Tailor Resume.",
  application: "Requires a saved job. Go to Jobs \u2192 click a job \u2192 Auto Apply.",
  web_scraper: "Runs automatically to scrape job boards. Toggle on to enable hourly scraping.",
  email_checker: "Requires Gmail OAuth token. Connect Gmail in Settings first.",
  recommendations: "Analyzes your profile and suggests improvements. Works automatically.",
  salary_negotiator: "Go to Salary Negotiator page to chat about offer negotiation.",
  linkedin_message: "Generates messages for saved recruiters. Add recruiters first.",
  linkedin_reply: "Checks your LinkedIn inbox for new messages and drafts replies.",
  ats_scorer: "Scores your resume against a job description. Go to Resumes \u2192 ATS Score.",
};

/* ── Component ─────────────────────────────────────────────────── */

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [dashboard, setDashboard] = useState<AgentDashboard | null>(null);
  const [history, setHistory] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);
  const [expandedHistory, setExpandedHistory] = useState(false);
  const [polling, setPolling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const [agentRes, statusRes, historyRes] = await Promise.all([
        agentsApi.list(),
        agentsApi.status(),
        agentsApi.history({ limit: 20 }),
      ]);
      const agentList = agentRes.data.agents ?? agentRes.data ?? [];
      const dash = statusRes.data;
      setAgents(agentList);
      setDashboard(dash);
      setHistory(historyRes.data.executions ?? historyRes.data ?? []);
      // Auto-stop polling when nothing is running
      const anyRunning = dash?.running > 0 || agentList.some((a: AgentInfo) => a.status === "running");
      if (!anyRunning && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setPolling(false);
      }
      return anyRunning;
    } catch {
      if (!silent) toast.error("Failed to load agents");
      return false;
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    setPolling(true);
    setExpandedHistory(true);
    pollRef.current = setInterval(() => load(true), 5000);
  }, [load]);

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [load]);

  const handleToggle = async (name: string) => {
    try {
      await agentsApi.toggle(name);
      toast.success(`Agent ${agentLabels[name] || name} toggled`);
      load();
    } catch {
      toast.error("Failed to toggle agent");
    }
  };

  const handleRun = async (name: string) => {
    setRunningAgent(name);
    try {
      await agentsApi.run(name);
      toast.success(`${agentLabels[name] || name} started — auto-refreshing until complete`);
      startPolling();
      setTimeout(() => load(true), 1500);
    } catch {
      toast.error(`Failed to run ${agentLabels[name] || name}`);
    } finally {
      setRunningAgent(null);
    }
  };

  const handlePipeline = async () => {
    const enabledAgents = agents.filter((a) => a.enabled).map((a) => a.name);
    if (enabledAgents.length === 0) {
      toast.error("No enabled agents to run");
      return;
    }
    try {
      await agentsApi.pipeline(enabledAgents);
      toast.success("Pipeline started — auto-refreshing until complete");
      startPolling();
      setTimeout(() => load(true), 2000);
    } catch {
      toast.error("Failed to start pipeline");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">AI Agents</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Manage and monitor your autonomous AI agents
          </p>
          {polling && (
            <p className="text-xs text-blue-500 flex items-center gap-1 mt-1">
              <FiRefreshCw className="h-3 w-3 animate-spin" /> Auto-refreshing every 5s…
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={() => load()} className="btn-secondary flex items-center gap-1 text-sm">
            <FiRefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button onClick={handlePipeline} className="btn-primary flex items-center gap-1 text-sm">
            <FiPlay className="h-4 w-4" /> Run All
          </button>
        </div>
      </div>

      {/* Stats row */}
      {dashboard && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="card text-center">
            <p className="text-2xl font-bold text-[var(--foreground)]">{dashboard.total}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Total Agents</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-green-500">{dashboard.enabled}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Enabled</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-blue-500">{dashboard.running}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Running Now</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-[var(--foreground)]">{history.length}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Recent Runs</p>
          </div>
        </div>
      )}

      {/* Agent cards grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className={`card transition-shadow hover:shadow-md ${
              !agent.enabled ? "opacity-60" : ""
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                {statusIcon[agent.status] || statusIcon.idle}
                <h3 className="font-semibold text-[var(--foreground)]">
                  {agentLabels[agent.name] || agent.name}
                </h3>
              </div>
              <button
                onClick={() => handleToggle(agent.name)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  agent.enabled ? "bg-brand-600" : "bg-gray-300 dark:bg-gray-600"
                }`}
                title={agent.enabled ? "Disable" : "Enable"}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    agent.enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
            <p className="text-xs text-[var(--muted-foreground)] mb-3 line-clamp-2">
              {agent.description}
            </p>
            {agentTriggerHint[agent.name] && (
              <p className="text-[10px] text-blue-500 dark:text-blue-400 mb-3 flex items-start gap-1">
                <FiInfo className="h-3 w-3 mt-0.5 flex-shrink-0" />
                {agentTriggerHint[agent.name]}
              </p>
            )}
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-[var(--muted-foreground)]">
                v{agent.version}
              </span>
              <button
                onClick={() => handleRun(agent.name)}
                disabled={!agent.enabled || runningAgent === agent.name}
                className="btn-secondary flex items-center gap-1 text-xs"
              >
                {runningAgent === agent.name ? (
                  <>
                    <FiRefreshCw className="h-3 w-3 animate-spin" /> Running...
                  </>
                ) : (
                  <>
                    <FiPlay className="h-3 w-3" /> Run Now
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Activity Log */}
      <div className="card">
        <button
          onClick={() => setExpandedHistory(!expandedHistory)}
          className="flex w-full items-center justify-between"
        >
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FiActivity className="h-4 w-4" /> Recent Activity
          </h3>
          {expandedHistory ? (
            <FiChevronUp className="h-4 w-4 text-[var(--muted-foreground)]" />
          ) : (
            <FiChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
          )}
        </button>

        {expandedHistory && (
          <div className="mt-4 overflow-x-auto">
            {history.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)] text-center py-4">
                No agent executions yet
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                    <th className="pb-2 font-medium">Agent</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Items</th>
                    <th className="pb-2 font-medium">Duration</th>
                    <th className="pb-2 font-medium">Started</th>
                    <th className="pb-2 font-medium">Error</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {history.map((exec) => (
                    <tr key={exec.id} className="hover:bg-[var(--muted)] transition-colors">
                      <td className="py-2 font-medium text-[var(--foreground)]">
                        {agentLabels[exec.agent_name] || exec.agent_name}
                      </td>
                      <td className="py-2">
                        <span
                          className={`badge ${
                            exec.status === "success"
                              ? "badge-green"
                              : exec.status === "failed"
                              ? "badge-red"
                              : exec.status === "running"
                              ? "badge-blue"
                              : "badge-gray"
                          }`}
                        >
                          {exec.status}
                        </span>
                      </td>
                      <td className="py-2 text-[var(--muted-foreground)]">
                        {exec.items_processed}
                      </td>
                      <td className="py-2 text-[var(--muted-foreground)]">
                        {exec.duration_seconds.toFixed(1)}s
                      </td>
                      <td className="py-2 text-[var(--muted-foreground)]">
                        {formatDate(exec.started_at)}
                      </td>
                      <td className="py-2 text-[var(--muted-foreground)] max-w-[200px]">
                        {exec.error_message && (
                          <span className="text-xs text-red-500 truncate block" title={exec.error_message}>
                            {exec.error_message.length > 60 ? exec.error_message.slice(0, 60) + "…" : exec.error_message}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
