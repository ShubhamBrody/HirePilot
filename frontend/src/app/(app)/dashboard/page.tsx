"use client";

import { useEffect, useState } from "react";
import { FiBriefcase, FiFileText, FiSend, FiUsers, FiTrendingUp } from "react-icons/fi";
import { applicationsApi, jobsApi } from "@/lib/api";

interface Stats {
  total_jobs: number;
  total_applications: number;
  total_resumes: number;
  total_recruiters: number;
  interview_rate: number;
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
  const [loading, setLoading] = useState(true);

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
    </div>
  );
}
