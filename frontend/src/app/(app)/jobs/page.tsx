"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { FiSearch, FiExternalLink, FiZap, FiLink, FiBarChart2, FiX, FiSend, FiLoader, FiTrash2 } from "react-icons/fi";
import { jobsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";

interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  source: string;
  source_url: string;
  match_score: number | null;
  match_reasoning: string | null;
  technologies: string | null;
  discovered_at: string;
  is_active: boolean;
  estimated_salary_breakdown: string | null;
}

interface FitReport {
  job_id: string;
  match_score: number;
  reasoning: string;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}

export default function JobsPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [scrapeKeywords, setScrapeKeywords] = useState("");
  const [scrapeLocation, setScrapeLocation] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState("");
  // Scrape URL
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [scrapingUrl, setScrapingUrl] = useState(false);
  // Fit report modal
  const [fitReport, setFitReport] = useState<FitReport | null>(null);
  const [scoringJobId, setScoringJobId] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await jobsApi.list({
        company: search || undefined,
        page_size: 50,
      });
      setJobs(data.jobs ?? []);
    } catch {
      toast.error("Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleSearch = async () => {
    if (!scrapeKeywords.trim()) {
      toast.error("Enter keywords to search");
      return;
    }
    setSearching(true);
    setSearchStatus(`Searching LinkedIn for "${scrapeKeywords}" jobs...`);
    try {
      const { data } = await jobsApi.searchLinkedIn({
        filters: {
          role: scrapeKeywords,
          location: scrapeLocation || undefined,
        },
        sources: ["linkedin"],
      });
      if (data.challenge) {
        toast.error("LinkedIn security challenge detected. Solve it via VNC (localhost:7900) and try again.");
      } else if (data.jobs?.length > 0) {
        toast.success(data.message || `Found ${data.jobs.length} jobs from LinkedIn`);
        setScrapeKeywords("");
        setScrapeLocation("");
        loadJobs();
      } else {
        toast.error("No jobs found on LinkedIn. Try different keywords.");
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to search for jobs";
      toast.error(msg);
    } finally {
      setSearching(false);
      setSearchStatus("");
    }
  };

  const handleScrapeUrl = async () => {
    if (!scrapeUrl.trim()) {
      toast.error("Enter a job URL");
      return;
    }
    setScrapingUrl(true);
    try {
      const { data } = await jobsApi.scrapeUrl({ url: scrapeUrl });
      if (data.error) {
        toast.error(data.error);
      } else {
        toast.success(`Scraped: ${data.job?.title} @ ${data.job?.company}`);
        setScrapeUrl("");
        loadJobs();
        if (data.fit_analysis) {
          setFitReport(data.fit_analysis);
        }
      }
    } catch {
      toast.error("Failed to scrape job URL");
    } finally {
      setScrapingUrl(false);
    }
  };

  const handleGetFitScore = async (jobId: string) => {
    setScoringJobId(jobId);
    try {
      const { data } = await jobsApi.getMatchScore(jobId);
      setFitReport(data);
      // Update the job in local state so the score renders immediately
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId ? { ...j, match_score: data.match_score, match_reasoning: data.reasoning } : j
        )
      );
    } catch {
      toast.error("Failed to compute fit score");
    } finally {
      setScoringJobId(null);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm("Move this job to trash?")) return;
    try {
      await jobsApi.delete(jobId);
      toast.success("Moved to trash");
      loadJobs();
    } catch {
      toast.error("Failed to delete job");
    }
  };

  const scoreColor = (score: number) => {
    if (score >= 0.8) return "text-green-500";
    if (score >= 0.6) return "text-yellow-500";
    return "text-red-500";
  };

  /** Salary comparison badge: compare job range mid-point to user CTC */
  const salaryBadge = (job: Job) => {
    if (!user?.current_salary_ctc || !job.estimated_salary_breakdown) return null;
    try {
      const sal = JSON.parse(job.estimated_salary_breakdown);
      const low = parseFloat(String(sal.base_low || sal.take_home_low || "0").replace(/[^0-9.]/g, ""));
      const high = parseFloat(String(sal.base_high || sal.take_home_high || "0").replace(/[^0-9.]/g, ""));
      if (!low || !high) return null;
      const mid = (low + high) / 2;
      const diff = ((mid - user.current_salary_ctc) / user.current_salary_ctc) * 100;
      if (diff > 5) {
        return (
          <span className="badge text-[10px] bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            ↑ {Math.round(diff)}% more
          </span>
        );
      } else if (diff < -5) {
        return (
          <span className="badge text-[10px] bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
            ↓ Below current
          </span>
        );
      }
      return (
        <span className="badge text-[10px] bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          ≈ Similar pay
        </span>
      );
    } catch {
      return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Jobs</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Discover and track job opportunities
          </p>
        </div>
      </div>

      {/* Discover panel */}
      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">
          <FiZap className="mr-1 inline h-4 w-4" /> Discover New Jobs
        </h3>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Keywords (e.g. Backend Engineer)"
            value={scrapeKeywords}
            onChange={(e) => setScrapeKeywords(e.target.value)}
            className="input max-w-xs"
            disabled={searching}
          />
          <input
            type="text"
            placeholder="Location (optional)"
            value={scrapeLocation}
            onChange={(e) => setScrapeLocation(e.target.value)}
            className="input max-w-xs"
            disabled={searching}
          />
          <button onClick={handleSearch} className="btn-primary" disabled={searching}>
            {searching ? (
              <span className="flex items-center gap-2">
                <FiLoader className="h-4 w-4 animate-spin" /> Searching...
              </span>
            ) : (
              "Start Search"
            )}
          </button>
        </div>
        {searching && (
          <div className="mt-3 flex items-center gap-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 px-4 py-3 border border-blue-200 dark:border-blue-800">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">{searchStatus}</p>
              <p className="text-xs text-blue-500 dark:text-blue-500 mt-0.5">
                Connecting to LinkedIn and scraping results — this may take 15-30 seconds
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Scrape URL panel */}
      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">
          <FiLink className="mr-1 inline h-4 w-4" /> Paste Job URL
        </h3>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="https://linkedin.com/jobs/view/..."
            value={scrapeUrl}
            onChange={(e) => setScrapeUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScrapeUrl()}
            className="input flex-1 min-w-[300px]"
          />
          <button
            onClick={handleScrapeUrl}
            disabled={scrapingUrl}
            className="btn-primary"
          >
            {scrapingUrl ? "Scraping..." : "Scrape & Analyze"}
          </button>
        </div>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Paste a job posting URL to extract details and get an AI fit analysis
        </p>
      </div>

      {/* Search filter */}
      <div className="relative">
        <FiSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
        <input
          type="text"
          placeholder="Filter jobs by company..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-10"
        />
      </div>

      {/* Job list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-[var(--muted-foreground)]">
            No jobs found. Try searching or pasting a job URL above.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const techs = job.technologies
              ? job.technologies.split(",").map((t) => t.trim()).filter(Boolean)
              : [];
            return (
              <div
                key={job.id}
                className="card flex items-center justify-between hover:shadow-md transition-shadow"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-[var(--foreground)]">
                      {job.title}
                    </h3>
                    <span className="badge badge-gray text-[10px] uppercase">
                      {job.source}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {job.company} · {job.location || "Remote"}
                  </p>
                  {techs.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {techs.slice(0, 5).map((tech) => (
                        <span key={tech} className="badge badge-blue text-[10px]">
                          {tech}
                        </span>
                      ))}
                      {techs.length > 5 && (
                        <span className="badge badge-gray text-[10px]">
                          +{techs.length - 5} more
                        </span>
                      )}
                    </div>
                  )}
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    Found {formatDate(job.discovered_at)}
                  </p>
                  {job.estimated_salary_breakdown && (() => {
                    try {
                      const sal = JSON.parse(job.estimated_salary_breakdown);
                      return (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {sal.take_home_low && sal.take_home_high && (
                            <span className="badge badge-green text-[10px]">
                              Take Home: {sal.take_home_low} - {sal.take_home_high}
                            </span>
                          )}
                          {sal.base_low && sal.base_high && (
                            <span className="badge badge-blue text-[10px]">
                              Base: {sal.base_low} - {sal.base_high}
                            </span>
                          )}
                          {sal.stocks_yearly && (
                            <span className="badge badge-gray text-[10px]">
                              Stock: {sal.stocks_yearly}/yr
                            </span>
                          )}
                        </div>
                      );
                    } catch {
                      return null;
                    }
                  })()}
                  {salaryBadge(job)}
                </div>
                <div className="flex items-center gap-3">
                  {job.match_score != null && job.match_score > 0 ? (
                    <div className="text-center">
                      <p className={`text-lg font-bold ${scoreColor(job.match_score)}`}>
                        {Math.round(job.match_score * 100)}%
                      </p>
                      <p className="text-[10px] text-[var(--muted-foreground)]">Match</p>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleGetFitScore(job.id)}
                      disabled={scoringJobId === job.id}
                      className="btn-secondary flex items-center gap-1 text-xs"
                      title="Compute AI Fit Score"
                    >
                      <FiBarChart2 className="h-3.5 w-3.5" />
                      {scoringJobId === job.id ? "..." : "Score"}
                    </button>
                  )}
                  <a
                    href={job.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary flex items-center gap-1"
                  >
                    <FiExternalLink className="h-4 w-4" /> View
                  </a>
                  <button
                    onClick={() => router.push(`/jobs/${job.id}/apply`)}
                    className="btn-primary flex items-center gap-1 text-sm"
                  >
                    <FiSend className="h-4 w-4" /> Apply
                  </button>
                  <button
                    onClick={() => handleDeleteJob(job.id)}
                    className="text-[var(--muted-foreground)] hover:text-red-500 transition-colors p-2"
                    title="Move to trash"
                  >
                    <FiTrash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Fit Report Modal */}
      {fitReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--card)] rounded-xl shadow-2xl w-full max-w-lg p-6 max-h-[80vh] overflow-y-auto relative">
            <button
              onClick={() => setFitReport(null)}
              className="absolute top-3 right-3 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              <FiX className="h-5 w-5" />
            </button>
            <h2 className="text-lg font-bold mb-4">AI Fit Report</h2>
            <div className="text-center mb-4">
              <span className={`text-4xl font-black ${scoreColor(fitReport.match_score)}`}>
                {Math.round(fitReport.match_score * 100)}%
              </span>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">Match Score</p>
            </div>
            {fitReport.reasoning && (
              <p className="text-sm mb-4">{fitReport.reasoning}</p>
            )}
            <div className="grid grid-cols-2 gap-4 text-sm">
              {fitReport.matched_skills.length > 0 && (
                <div>
                  <h4 className="font-semibold text-green-500 mb-1">Matched Skills</h4>
                  <div className="flex flex-wrap gap-1">
                    {fitReport.matched_skills.map((s) => (
                      <span key={s} className="badge badge-green text-[10px]">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {fitReport.missing_skills.length > 0 && (
                <div>
                  <h4 className="font-semibold text-red-500 mb-1">Missing Skills</h4>
                  <div className="flex flex-wrap gap-1">
                    {fitReport.missing_skills.map((s) => (
                      <span key={s} className="badge badge-red text-[10px]">{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {fitReport.strengths.length > 0 && (
              <div className="mt-4">
                <h4 className="font-semibold text-sm mb-1">Strengths</h4>
                <ul className="text-xs space-y-1 list-disc list-inside">
                  {fitReport.strengths.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            {fitReport.weaknesses.length > 0 && (
              <div className="mt-3">
                <h4 className="font-semibold text-sm mb-1">Weaknesses</h4>
                <ul className="text-xs space-y-1 list-disc list-inside">
                  {fitReport.weaknesses.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            {fitReport.recommendations.length > 0 && (
              <div className="mt-3">
                <h4 className="font-semibold text-sm mb-1">Recommendations</h4>
                <ul className="text-xs space-y-1 list-disc list-inside">
                  {fitReport.recommendations.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
