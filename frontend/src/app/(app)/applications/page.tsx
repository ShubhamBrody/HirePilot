"use client";

import { useEffect, useState, useCallback } from "react";
import { FiFilter, FiArrowRight } from "react-icons/fi";
import { applicationsApi } from "@/lib/api";
import { formatDate, statusColors, capitalize } from "@/lib/utils";
import toast from "react-hot-toast";

interface Application {
  id: string;
  job_title: string;
  company: string;
  status: string;
  method: string;
  applied_date: string | null;
  interview_date: string | null;
  notes: string | null;
}

const STATUSES = [
  "saved",
  "applied",
  "screening",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "no_response",
];

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadApplications = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, unknown> = { limit: 100 };
      if (statusFilter !== "all") params.status = statusFilter;
      const { data } = await applicationsApi.list(params);
      setApplications(data.applications ?? []);
    } catch {
      toast.error("Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadApplications();
  }, [loadApplications]);

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await applicationsApi.updateStatus(id, { status: newStatus });
      toast.success(`Status updated to ${capitalize(newStatus)}`);
      loadApplications();
    } catch {
      toast.error("Failed to update status");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Applications</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Track your job application pipeline
          </p>
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setStatusFilter("all")}
          className={`badge cursor-pointer ${
            statusFilter === "all" ? "badge-blue" : "badge-gray"
          }`}
        >
          All
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`badge cursor-pointer ${
              statusFilter === s ? statusColors[s] || "badge-gray" : "badge-gray"
            }`}
          >
            {capitalize(s.replace("_", " "))}
          </button>
        ))}
      </div>

      {/* Applications table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        </div>
      ) : applications.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-[var(--muted-foreground)]">
            No applications found. Apply to jobs to start tracking.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="pb-3 font-medium">Position</th>
                <th className="pb-3 font-medium">Company</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">Method</th>
                <th className="pb-3 font-medium">Applied</th>
                <th className="pb-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {applications.map((app) => (
                <tr key={app.id} className="hover:bg-[var(--muted)] transition-colors">
                  <td className="py-3 font-medium text-[var(--foreground)]">
                    {app.job_title}
                  </td>
                  <td className="py-3 text-[var(--muted-foreground)]">
                    {app.company}
                  </td>
                  <td className="py-3">
                    <span className={`badge ${statusColors[app.status] || "badge-gray"}`}>
                      {capitalize(app.status.replace("_", " "))}
                    </span>
                  </td>
                  <td className="py-3 text-[var(--muted-foreground)]">
                    {capitalize(app.method.replace("_", " "))}
                  </td>
                  <td className="py-3 text-[var(--muted-foreground)]">
                    {formatDate(app.applied_date)}
                  </td>
                  <td className="py-3">
                    <select
                      value=""
                      onChange={(e) => {
                        if (e.target.value) handleStatusChange(app.id, e.target.value);
                      }}
                      className="input text-xs py-1 max-w-[140px]"
                    >
                      <option value="">Move to...</option>
                      {STATUSES.filter((s) => s !== app.status).map((s) => (
                        <option key={s} value={s}>
                          {capitalize(s.replace("_", " "))}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
