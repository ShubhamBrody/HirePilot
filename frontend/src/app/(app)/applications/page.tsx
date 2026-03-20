"use client";

import { useEffect, useState, useCallback } from "react";
import { FiFilter, FiArrowRight, FiFileText, FiX, FiMail, FiChevronDown, FiChevronUp, FiTrash2, FiLoader } from "react-icons/fi";
import { applicationsApi, agentsApi, resumesApi } from "@/lib/api";
import { formatDate, statusColors, capitalize } from "@/lib/utils";
import toast from "react-hot-toast";

interface Application {
  id: string;
  job_title: string;
  company: string;
  role: string;
  status: string;
  method: string;
  applied_date: string | null;
  interview_date: string | null;
  notes: string | null;
  resume_version_id: string | null;
}

interface ResumePreview {
  application_id: string;
  resume_version_id: string;
  resume_name: string;
  latex_source: string;
  company: string;
  role: string;
}

const STATUSES = [
  "draft",
  "applying",
  "applied",
  "viewed",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [resumePreview, setResumePreview] = useState<ResumePreview | null>(null);
  const [resumePdfUrl, setResumePdfUrl] = useState<string | null>(null);
  const [resumePdfLoading, setResumePdfLoading] = useState(false);
  const [emailHistory, setEmailHistory] = useState<Array<{
    id: string;
    agent_name: string;
    status: string;
    result: string | null;
    started_at: string;
    items_processed: number;
  }>>([]);
  const [showEmails, setShowEmails] = useState(false);

  const loadApplications = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, unknown> = { limit: 100 };
      if (statusFilter !== "all") params.status = statusFilter;
      const { data } = await applicationsApi.list(params);
      setApplications(data.applications ?? []);
      // Load email check history
      try {
        const emailRes = await agentsApi.history({ agent_name: "email_checker", limit: 10 });
        setEmailHistory(emailRes.data.executions ?? []);
      } catch { /* email history not critical */ }
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

  const handleDeleteApplication = async (id: string) => {
    if (!confirm("Move this application to trash?")) return;
    try {
      await applicationsApi.delete(id);
      toast.success("Moved to trash");
      loadApplications();
    } catch {
      toast.error("Failed to delete application");
    }
  };

  const handleViewResume = async (applicationId: string) => {
    try {
      const { data } = await applicationsApi.getResume(applicationId);
      setResumePreview(data);
      // Auto-compile to PDF
      if (data.latex_source) {
        setResumePdfLoading(true);
        setResumePdfUrl(null);
        try {
          const pdfResp = await resumesApi.compilePreview(data.latex_source);
          const url = URL.createObjectURL(pdfResp.data);
          setResumePdfUrl(url);
        } catch {
          // Fall back to showing LaTeX if compile fails
        } finally {
          setResumePdfLoading(false);
        }
      }
    } catch {
      toast.error("Resume not available for this application");
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
                <th className="pb-3 font-medium">Resume</th>
                <th className="pb-3 font-medium">Applied</th>
                <th className="pb-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {applications.map((app) => (
                <tr key={app.id} className="hover:bg-[var(--muted)] transition-colors">
                  <td className="py-3 font-medium text-[var(--foreground)]">
                    {app.role || app.job_title}
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
                  <td className="py-3">
                    <button
                      onClick={() => handleViewResume(app.id)}
                      className="text-brand-600 hover:text-brand-700 text-xs flex items-center gap-1"
                      title="View the resume sent for this application"
                    >
                      <FiFileText className="h-3.5 w-3.5" /> View
                    </button>
                  </td>
                  <td className="py-3 text-[var(--muted-foreground)]">
                    {formatDate(app.applied_date)}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
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
                      <button
                        onClick={() => handleDeleteApplication(app.id)}
                        className="text-[var(--muted-foreground)] hover:text-red-500 transition-colors"
                        title="Move to trash"
                      >
                        <FiTrash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Email Tracking Section */}
      <div className="card">
        <button
          onClick={() => setShowEmails(!showEmails)}
          className="flex w-full items-center justify-between"
        >
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FiMail className="h-4 w-4" /> Email Tracking History
          </h3>
          {showEmails ? (
            <FiChevronUp className="h-4 w-4 text-[var(--muted-foreground)]" />
          ) : (
            <FiChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
          )}
        </button>
        {showEmails && (
          <div className="mt-4">
            {emailHistory.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)] text-center py-4">
                No email checks yet. The Email Checker agent runs hourly to scan your Gmail for application updates.
              </p>
            ) : (
              <div className="space-y-2">
                {emailHistory.map((exec) => {
                  let resultData: { emails_classified?: number; statuses_updated?: number } = {};
                  try { if (exec.result) resultData = JSON.parse(exec.result); } catch { /* ignore */ }
                  return (
                    <div key={exec.id} className="flex items-center justify-between p-2 rounded bg-[var(--muted)]">
                      <div>
                        <p className="text-sm font-medium text-[var(--foreground)]">
                          Email Check
                          <span className={`ml-2 badge ${exec.status === "success" ? "badge-green" : exec.status === "failed" ? "badge-red" : "badge-gray"}`}>
                            {exec.status}
                          </span>
                        </p>
                        <p className="text-xs text-[var(--muted-foreground)]">
                          {exec.items_processed} emails processed
                          {resultData.statuses_updated ? ` | ${resultData.statuses_updated} statuses updated` : ""}
                        </p>
                      </div>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {formatDate(exec.started_at)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Resume Preview Modal */}
      {resumePreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--card)] rounded-xl shadow-2xl w-full max-w-3xl p-6 max-h-[85vh] overflow-hidden flex flex-col relative">
            <button
              onClick={() => { setResumePreview(null); if (resumePdfUrl) { URL.revokeObjectURL(resumePdfUrl); setResumePdfUrl(null); } }}
              className="absolute top-3 right-3 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              <FiX className="h-5 w-5" />
            </button>
            <h2 className="text-lg font-bold mb-1">
              Resume: {resumePreview.resume_name}
            </h2>
            <p className="text-sm text-[var(--muted-foreground)] mb-3">
              Used for {resumePreview.role} @ {resumePreview.company}
            </p>
            <div className="flex-1 min-h-0">
              {resumePdfLoading ? (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <FiLoader className="h-8 w-8 animate-spin text-brand-500" />
                  <p className="text-sm text-[var(--muted-foreground)]">Compiling PDF...</p>
                </div>
              ) : resumePdfUrl ? (
                <iframe
                  src={`${resumePdfUrl}#toolbar=0&navpanes=0&scrollbar=1&view=FitH`}
                  className="w-full h-full border-0 rounded-lg"
                  style={{ minHeight: "60vh" }}
                  title="Resume PDF"
                />
              ) : (
                <pre className="flex-1 overflow-auto bg-[var(--muted)] rounded-lg p-4 text-xs font-mono whitespace-pre-wrap h-full">
                  {resumePreview.latex_source}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
