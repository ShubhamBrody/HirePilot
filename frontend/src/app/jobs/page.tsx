"use client";

import { useEffect, useState, useCallback } from "react";
import { FiSearch, FiFilter, FiExternalLink, FiZap } from "react-icons/fi";
import { jobsApi } from "@/lib/api";
import { formatDate, statusColors, truncate } from "@/lib/utils";
import toast from "react-hot-toast";

interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  source: string;
  match_score: number | null;
  url: string;
  created_at: string;
  skills: string[];
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [scrapeKeywords, setScrapeKeywords] = useState("");
  const [scrapeLocation, setScrapeLocation] = useState("");

  const loadJobs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await jobsApi.list({
        search: search || undefined,
        limit: 50,
      });
      setJobs(data.items || []);
    } catch {
      toast.error("Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleScrape = async () => {
    if (!scrapeKeywords.trim()) {
      toast.error("Enter keywords to search");
      return;
    }
    try {
      await jobsApi.triggerScrape({
        keywords: scrapeKeywords.split(",").map((k) => k.trim()),
        location: scrapeLocation || undefined,
      });
      toast.success("Job scraping started! Results will appear shortly.");
      setScrapeKeywords("");
      setScrapeLocation("");
    } catch {
      toast.error("Failed to start job scrape");
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

      {/* Scrape panel */}
      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">
          <FiZap className="mr-1 inline h-4 w-4" /> Discover New Jobs
        </h3>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Keywords (comma-separated)"
            value={scrapeKeywords}
            onChange={(e) => setScrapeKeywords(e.target.value)}
            className="input max-w-xs"
          />
          <input
            type="text"
            placeholder="Location (optional)"
            value={scrapeLocation}
            onChange={(e) => setScrapeLocation(e.target.value)}
            className="input max-w-xs"
          />
          <button onClick={handleScrape} className="btn-primary">
            Start Scraping
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <FiSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
        <input
          type="text"
          placeholder="Search jobs by title, company, skills..."
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
            No jobs found. Try scraping for new opportunities above.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
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
                {job.skills?.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {job.skills.slice(0, 5).map((skill) => (
                      <span key={skill} className="badge badge-blue text-[10px]">
                        {skill}
                      </span>
                    ))}
                    {job.skills.length > 5 && (
                      <span className="badge badge-gray text-[10px]">
                        +{job.skills.length - 5} more
                      </span>
                    )}
                  </div>
                )}
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  Found {formatDate(job.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {job.match_score != null && (
                  <div className="text-center">
                    <p className="text-lg font-bold text-brand-600">
                      {job.match_score}%
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)]">Match</p>
                  </div>
                )}
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary flex items-center gap-1"
                >
                  <FiExternalLink className="h-4 w-4" /> View
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
