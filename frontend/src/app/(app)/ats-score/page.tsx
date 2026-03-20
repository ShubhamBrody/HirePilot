"use client";

import { useEffect, useState, useCallback } from "react";
import {
  FiTarget,
  FiRefreshCw,
  FiCheckCircle,
  FiAlertTriangle,
  FiXCircle,
  FiArrowUp,
  FiLoader,
  FiFileText,
  FiBriefcase,
} from "react-icons/fi";
import { resumesApi, jobsApi } from "@/lib/api";
import toast from "react-hot-toast";

interface ResumeVersion {
  id: string;
  name: string;
  is_master: boolean;
}

interface Job {
  id: string;
  title: string;
  company: string;
}

interface ATSResult {
  overall_score: number;
  breakdown: Record<string, number>;
  matched_keywords: string[];
  missing_keywords: string[];
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  summary: string;
}

function ScoreRing({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : score >= 40 ? "#f97316" : "#ef4444";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--border)" strokeWidth="8" fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth="8"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>
          {score}
        </span>
        <span className="text-[10px] text-[var(--muted-foreground)]">/ 100</span>
      </div>
    </div>
  );
}

const breakdownLabels: Record<string, string> = {
  keyword_match: "Keyword Match",
  formatting: "ATS Formatting",
  experience_relevance: "Experience Fit",
  skills_alignment: "Skills Match",
  education_fit: "Education Fit",
  quantification: "Quantification",
};

export default function ATSScorePage() {
  const [resumes, setResumes] = useState<ResumeVersion[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedResume, setSelectedResume] = useState("");
  const [selectedJob, setSelectedJob] = useState("");
  const [customJD, setCustomJD] = useState("");
  const [useCustomJD, setUseCustomJD] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ATSResult | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [resumeRes, jobRes] = await Promise.all([resumesApi.list(), jobsApi.list()]);
      const rl = resumeRes.data.resumes ?? resumeRes.data ?? [];
      const jl = jobRes.data.jobs ?? jobRes.data ?? [];
      setResumes(rl);
      setJobs(jl);
      // Auto-select master resume
      const master = rl.find((r: ResumeVersion) => r.is_master);
      if (master) setSelectedResume(master.id);
    } catch {
      toast.error("Failed to load data");
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScore = async () => {
    if (!selectedResume && !useCustomJD) {
      toast.error("Select a resume");
      return;
    }
    if (!selectedJob && !customJD) {
      toast.error("Select a job or paste a job description");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const payload: Record<string, string> = {};
      if (selectedResume) payload.resume_id = selectedResume;
      if (useCustomJD && customJD) {
        payload.job_description = customJD;
      } else if (selectedJob) {
        payload.job_id = selectedJob;
      }
      const { data } = await resumesApi.atsScore(payload);
      setResult(data);
      toast.success(`ATS Score: ${data.overall_score}/100`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Scoring failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = (s: number) =>
    s >= 80 ? "text-green-500" : s >= 60 ? "text-yellow-500" : s >= 40 ? "text-orange-500" : "text-red-500";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
          <FiTarget className="h-6 w-6 text-brand-600" /> ATS Resume Scorer
        </h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Check how well your resume matches a job description from an ATS perspective
        </p>
      </div>

      {/* Input Card */}
      <div className="card space-y-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* Resume selector */}
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              <FiFileText className="inline h-4 w-4 mr-1 -mt-0.5" /> Resume
            </label>
            <select
              value={selectedResume}
              onChange={(e) => setSelectedResume(e.target.value)}
              className="input w-full"
            >
              <option value="">— Select resume —</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} {r.is_master ? "(Master)" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Job selector */}
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
              <FiBriefcase className="inline h-4 w-4 mr-1 -mt-0.5" /> Job
            </label>
            {!useCustomJD ? (
              <div className="flex gap-2">
                <select
                  value={selectedJob}
                  onChange={(e) => setSelectedJob(e.target.value)}
                  className="input flex-1"
                >
                  <option value="">— Select saved job —</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title} @ {j.company}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setUseCustomJD(true)}
                  className="btn-secondary text-xs whitespace-nowrap"
                >
                  Paste JD
                </button>
              </div>
            ) : (
              <div>
                <textarea
                  value={customJD}
                  onChange={(e) => setCustomJD(e.target.value)}
                  placeholder="Paste the full job description here..."
                  rows={4}
                  className="input w-full"
                />
                <button
                  onClick={() => {
                    setUseCustomJD(false);
                    setCustomJD("");
                  }}
                  className="text-xs text-[var(--muted-foreground)] mt-1 hover:underline"
                >
                  ← Back to saved jobs
                </button>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={handleScore}
          disabled={loading}
          className="btn-primary flex items-center gap-2"
        >
          {loading ? (
            <>
              <FiLoader className="h-4 w-4 animate-spin" /> Analyzing...
            </>
          ) : (
            <>
              <FiTarget className="h-4 w-4" /> Score Resume
            </>
          )}
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center py-12 gap-2">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          <p className="text-sm text-[var(--muted-foreground)]">
            AI is analyzing your resume against the job description...
          </p>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-6">
          {/* Overall Score */}
          <div className="card flex flex-col items-center md:flex-row md:items-start gap-6">
            <ScoreRing score={result.overall_score} />
            <div className="flex-1">
              <h2 className="text-lg font-bold text-[var(--foreground)] mb-1">ATS Compatibility Score</h2>
              <p className="text-sm text-[var(--muted-foreground)]">{result.summary}</p>
            </div>
          </div>

          {/* Breakdown */}
          <div className="card">
            <h3 className="font-semibold text-[var(--foreground)] mb-3">Score Breakdown</h3>
            <div className="space-y-3">
              {Object.entries(result.breakdown).map(([key, value]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-[var(--foreground)]">{breakdownLabels[key] || key}</span>
                    <span className={`font-semibold ${scoreColor(value)}`}>{value}/100</span>
                  </div>
                  <div className="h-2 rounded-full bg-[var(--muted)]">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${value}%`,
                        backgroundColor:
                          value >= 80 ? "#22c55e" : value >= 60 ? "#eab308" : value >= 40 ? "#f97316" : "#ef4444",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Keywords */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="card">
              <h3 className="font-semibold text-green-600 flex items-center gap-1 mb-2">
                <FiCheckCircle className="h-4 w-4" /> Matched Keywords ({result.matched_keywords.length})
              </h3>
              <div className="flex flex-wrap gap-1">
                {result.matched_keywords.map((kw, i) => (
                  <span key={i} className="badge badge-green text-[10px]">
                    {kw}
                  </span>
                ))}
                {result.matched_keywords.length === 0 && (
                  <p className="text-xs text-[var(--muted-foreground)]">None found</p>
                )}
              </div>
            </div>
            <div className="card">
              <h3 className="font-semibold text-red-500 flex items-center gap-1 mb-2">
                <FiXCircle className="h-4 w-4" /> Missing Keywords ({result.missing_keywords.length})
              </h3>
              <div className="flex flex-wrap gap-1">
                {result.missing_keywords.map((kw, i) => (
                  <span key={i} className="badge badge-red text-[10px]">
                    {kw}
                  </span>
                ))}
                {result.missing_keywords.length === 0 && (
                  <p className="text-xs text-[var(--muted-foreground)]">None — great coverage!</p>
                )}
              </div>
            </div>
          </div>

          {/* Strengths & Weaknesses */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="card">
              <h3 className="font-semibold text-green-600 flex items-center gap-1 mb-2">
                <FiArrowUp className="h-4 w-4" /> Strengths
              </h3>
              <ul className="space-y-1">
                {result.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-[var(--foreground)] flex items-start gap-2">
                    <span className="text-green-500 mt-0.5">✓</span> {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="card">
              <h3 className="font-semibold text-orange-500 flex items-center gap-1 mb-2">
                <FiAlertTriangle className="h-4 w-4" /> Weaknesses
              </h3>
              <ul className="space-y-1">
                {result.weaknesses.map((w, i) => (
                  <li key={i} className="text-sm text-[var(--foreground)] flex items-start gap-2">
                    <span className="text-orange-500 mt-0.5">!</span> {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Suggestions */}
          {result.suggestions.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-[var(--foreground)] flex items-center gap-1 mb-2">
                <FiRefreshCw className="h-4 w-4 text-brand-600" /> Improvement Suggestions
              </h3>
              <ol className="space-y-2 list-decimal ml-5">
                {result.suggestions.map((s, i) => (
                  <li key={i} className="text-sm text-[var(--foreground)]">
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
