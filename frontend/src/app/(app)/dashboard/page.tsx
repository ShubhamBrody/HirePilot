"use client";

import { useEffect, useState } from "react";
import {
  FiBriefcase,
  FiFileText,
  FiSend,
  FiUsers,
  FiTrendingUp,
  FiInfo,
  FiCheckCircle,
  FiAlertTriangle,
  FiBarChart2,
  FiDollarSign,
  FiActivity,
} from "react-icons/fi";
import { applicationsApi, jobsApi, insightsApi } from "@/lib/api";

interface Stats {
  total_jobs: number;
  total_applications: number;
  total_resumes: number;
  total_recruiters: number;
  interview_rate: number;
}

interface SkillInsight {
  skill: string;
  frequency: number;
  percentage: number;
  user_has: boolean;
}

interface SkillsInsights {
  total_jobs_analyzed: number;
  target_role: string | null;
  top_skills: SkillInsight[];
  matched_skills: SkillInsight[];
  missing_skills: SkillInsight[];
  did_you_know: string[];
}

interface HiringTrend {
  company: string;
  active_listings: number;
  roles: string[];
}

interface HiringTrends {
  total_companies: number;
  total_active_jobs: number;
  top_companies: HiringTrend[];
  trending_roles: string[];
  period_days: number;
}

interface SalaryAnalysis {
  user_ctc: number | null;
  salary_currency: string;
  market_median: number | null;
  market_min: number | null;
  market_max: number | null;
  jobs_with_salary: number;
  total_jobs: number;
  percent_vs_market: number | null;
  recommendation: string;
}

const defaultStats: Stats = {
  total_jobs: 0,
  total_applications: 0,
  total_resumes: 0,
  total_recruiters: 0,
  interview_rate: 0,
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>(defaultStats);
  const [recentJobs, setRecentJobs] = useState<Array<Record<string, unknown>>>([]);
  const [insights, setInsights] = useState<SkillsInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [hiringTrends, setHiringTrends] = useState<HiringTrends | null>(null);
  const [hiringLoading, setHiringLoading] = useState(true);
  const [salaryAnalysis, setSalaryAnalysis] = useState<SalaryAnalysis | null>(null);
  const [salaryLoading, setSalaryLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [analyticsRes, jobsRes] = await Promise.all([
          applicationsApi.analytics(),
          jobsApi.list({ limit: 5, sort: "-created_at" }),
        ]);
        setStats(analyticsRes.data);
        setRecentJobs(jobsRes.data.jobs ?? []);
      } catch {
        // Silently handle — dashboard degrades gracefully
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Load skills insights separately (can be slower due to LLM)
  useEffect(() => {
    async function loadInsights() {
      try {
        const { data } = await insightsApi.skills();
        setInsights(data);
      } catch {
        // Silently handle
      } finally {
        setInsightsLoading(false);
      }
    }
    loadInsights();
  }, []);

  // Load hiring trends
  useEffect(() => {
    async function loadHiring() {
      try {
        const { data } = await insightsApi.hiringTrends();
        setHiringTrends(data);
      } catch {
        // Silently handle
      } finally {
        setHiringLoading(false);
      }
    }
    loadHiring();
  }, []);

  // Load salary analysis
  useEffect(() => {
    async function loadSalary() {
      try {
        const { data } = await insightsApi.salaryAnalysis();
        setSalaryAnalysis(data);
      } catch {
        // Silently handle
      } finally {
        setSalaryLoading(false);
      }
    }
    loadSalary();
  }, []);

  const statCards = [
    { label: "Jobs Found", value: stats.total_jobs, icon: FiBriefcase, color: "text-blue-600" },
    { label: "Applications", value: stats.total_applications, icon: FiSend, color: "text-green-600" },
    { label: "Resumes", value: stats.total_resumes, icon: FiFileText, color: "text-purple-600" },
    { label: "Recruiters", value: stats.total_recruiters, icon: FiUsers, color: "text-orange-600" },
    { label: "Interview Rate", value: `${stats.interview_rate}%`, icon: FiTrendingUp, color: "text-emerald-600" },
  ];

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Dashboard</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Your job search at a glance
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card">
            <div className="flex items-center gap-3">
              <div className={`rounded-lg bg-[var(--muted)] p-2.5 ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[var(--foreground)]">{value}</p>
                <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent jobs */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)]">
          Latest Job Discoveries
        </h2>
        {recentJobs.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">
            No jobs found yet. Start a job scrape to discover opportunities.
          </p>
        ) : (
          <div className="space-y-3">
            {recentJobs.map((job: Record<string, unknown>) => (
              <div
                key={job.id as string}
                className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3"
              >
                <div>
                  <p className="font-medium text-[var(--foreground)]">
                    {job.title as string}
                  </p>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {job.company as string} · {(job.location as string) || "Remote"}
                  </p>
                </div>
                {job.match_score != null && (
                  <span className="badge badge-green">
                    {job.match_score as number}% match
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Did You Know? — Skills Insights Widget */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
          <FiInfo className="h-5 w-5 text-brand-600" /> Did You Know?
        </h2>

        {insightsLoading ? (
          <div className="flex justify-center py-6">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          </div>
        ) : !insights || insights.total_jobs_analyzed === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">
            Start discovering jobs to get personalized skill insights!
          </p>
        ) : (
          <div className="space-y-5">
            {/* Insights nuggets */}
            {insights.did_you_know.length > 0 && (
              <div className="space-y-2">
                {insights.did_you_know.map((nugget, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 p-3 rounded-lg bg-brand-50 dark:bg-brand-900/20 text-sm"
                  >
                    <FiInfo className="h-4 w-4 text-brand-600 mt-0.5 shrink-0" />
                    <span className="text-[var(--foreground)]">
                      {nugget.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
                        part.startsWith("**") && part.endsWith("**") ? (
                          <strong key={j} className="text-brand-600">
                            {part.slice(2, -2)}
                          </strong>
                        ) : (
                          <span key={j}>{part}</span>
                        )
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Target role */}
            {insights.target_role && (
              <p className="text-xs text-[var(--muted-foreground)]">
                Based on {insights.total_jobs_analyzed} jobs analyzed for{" "}
                <strong>{insights.target_role}</strong> roles
              </p>
            )}

            {/* Top skills bar chart */}
            {insights.top_skills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-1">
                  <FiBarChart2 className="h-4 w-4" /> Most In-Demand Skills
                </h3>
                <div className="space-y-2">
                  {insights.top_skills.slice(0, 10).map((skill) => (
                    <div key={skill.skill} className="flex items-center gap-2">
                      <div className="w-28 text-xs truncate flex items-center gap-1">
                        {skill.user_has ? (
                          <FiCheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                        ) : (
                          <FiAlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
                        )}
                        <span className={skill.user_has ? "text-green-600 dark:text-green-400" : ""}>
                          {skill.skill}
                        </span>
                      </div>
                      <div className="flex-1 bg-[var(--muted)] rounded-full h-2.5">
                        <div
                          className={`h-2.5 rounded-full transition-all ${
                            skill.user_has
                              ? "bg-green-500"
                              : "bg-amber-500"
                          }`}
                          style={{ width: `${Math.min(skill.percentage, 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-[var(--muted-foreground)] w-10 text-right">
                        {skill.percentage}%
                      </span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-4 mt-3 text-[10px] text-[var(--muted-foreground)]">
                  <span className="flex items-center gap-1">
                    <FiCheckCircle className="h-3 w-3 text-green-500" /> You have this
                  </span>
                  <span className="flex items-center gap-1">
                    <FiAlertTriangle className="h-3 w-3 text-amber-500" /> Opportunity to learn
                  </span>
                </div>
              </div>
            )}

            {/* Missing skills highlight */}
            {insights.missing_skills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Top Skills to Learn</h3>
                <div className="flex flex-wrap gap-1.5">
                  {insights.missing_skills.slice(0, 8).map((skill) => (
                    <span
                      key={skill.skill}
                      className="badge badge-amber text-[10px] flex items-center gap-1"
                    >
                      {skill.skill} ({skill.percentage}%)
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hiring Trends & Salary Insights — side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Companies Hiring Now */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
            <FiActivity className="h-5 w-5 text-blue-600" /> Companies Hiring Now
          </h2>
          {hiringLoading ? (
            <div className="flex justify-center py-6">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
            </div>
          ) : !hiringTrends || hiringTrends.total_active_jobs === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No hiring data yet. Discover more jobs to see trends.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-4 text-sm">
                <div className="text-center">
                  <p className="text-xl font-bold text-[var(--foreground)]">{hiringTrends.total_companies}</p>
                  <p className="text-[10px] text-[var(--muted-foreground)]">Companies</p>
                </div>
                <div className="text-center">
                  <p className="text-xl font-bold text-[var(--foreground)]">{hiringTrends.total_active_jobs}</p>
                  <p className="text-[10px] text-[var(--muted-foreground)]">Active Jobs</p>
                </div>
              </div>
              <div className="space-y-2">
                {hiringTrends.top_companies.slice(0, 8).map((c) => (
                  <div key={c.company} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-[var(--foreground)]">{c.company}</p>
                      <p className="text-[10px] text-[var(--muted-foreground)] truncate max-w-[200px]">
                        {c.roles.slice(0, 2).join(", ")}
                      </p>
                    </div>
                    <span className="badge badge-blue text-[10px]">{c.active_listings} listings</span>
                  </div>
                ))}
              </div>
              {hiringTrends.trending_roles.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-[var(--muted-foreground)] mb-1">Trending Roles</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {hiringTrends.trending_roles.slice(0, 6).map((role) => (
                      <span key={role} className="badge badge-gray text-[10px]">{role}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Salary Insights */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
            <FiDollarSign className="h-5 w-5 text-green-600" /> Salary Insights
          </h2>
          {salaryLoading ? (
            <div className="flex justify-center py-6">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
            </div>
          ) : !salaryAnalysis ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              Set your salary in settings to see how you compare.
            </p>
          ) : salaryAnalysis.jobs_with_salary === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No salary data available yet. Discover more jobs for salary analysis.
            </p>
          ) : (
            <div className="space-y-4">
              {salaryAnalysis.user_ctc != null && salaryAnalysis.market_median != null && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-[var(--muted)] p-3 text-center">
                    <p className="text-lg font-bold text-[var(--foreground)]">
                      {salaryAnalysis.salary_currency} {salaryAnalysis.user_ctc.toLocaleString()}
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)]">Your CTC</p>
                  </div>
                  <div className="rounded-lg bg-[var(--muted)] p-3 text-center">
                    <p className="text-lg font-bold text-[var(--foreground)]">
                      {salaryAnalysis.salary_currency} {salaryAnalysis.market_median.toLocaleString()}
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)]">Market Median</p>
                  </div>
                </div>
              )}
              {salaryAnalysis.percent_vs_market != null && (
                <div className={`rounded-lg p-3 text-center ${
                  salaryAnalysis.percent_vs_market > 0
                    ? "bg-green-50 dark:bg-green-950/30"
                    : "bg-amber-50 dark:bg-amber-950/30"
                }`}>
                  <span className={`text-2xl font-bold ${
                    salaryAnalysis.percent_vs_market > 0 ? "text-green-600" : "text-amber-600"
                  }`}>
                    {salaryAnalysis.percent_vs_market > 0 ? "+" : ""}{salaryAnalysis.percent_vs_market}%
                  </span>
                  <p className="text-xs text-[var(--muted-foreground)] mt-1">vs. Market Median</p>
                </div>
              )}
              {salaryAnalysis.market_min != null && salaryAnalysis.market_max != null && (
                <div className="text-xs text-[var(--muted-foreground)]">
                  Market range: {salaryAnalysis.salary_currency} {salaryAnalysis.market_min.toLocaleString()} – {salaryAnalysis.market_max.toLocaleString()}
                  <span className="ml-2">({salaryAnalysis.jobs_with_salary} of {salaryAnalysis.total_jobs} jobs with salary data)</span>
                </div>
              )}
              {salaryAnalysis.recommendation && (
                <div className="rounded-lg bg-brand-50 dark:bg-brand-900/20 p-3 text-sm text-[var(--foreground)]">
                  {salaryAnalysis.recommendation}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
