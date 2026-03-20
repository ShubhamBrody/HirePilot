"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  FiCheck,
  FiEdit3,
  FiLoader,
  FiSend,
  FiPlay,
  FiArrowLeft,
  FiMessageCircle,
  FiFileText,
  FiZap,
  FiCheckCircle,
  FiAlertCircle,
} from "react-icons/fi";
import { applicationsApi, jobsApi, resumesApi } from "@/lib/api";
import toast from "react-hot-toast";

/* ── Types ──────────────────────────────────────────────────────── */

interface WizardStep {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  latex?: string | null;
}

const STEPS: WizardStep[] = [
  { id: "confirm_tailor", label: "Start", icon: FiZap },
  { id: "review_resume", label: "Review Resume", icon: FiEdit3 },
  { id: "confirm_apply", label: "Approve & Save", icon: FiCheck },
  { id: "applying", label: "Applying", icon: FiPlay },
  { id: "done", label: "Done", icon: FiCheckCircle },
];

/* ── Component ──────────────────────────────────────────────────── */

export default function ApplyWizardPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  // Wizard state
  const [step, setStep] = useState<string>("loading");
  const [wizardId, setWizardId] = useState<string>("");
  const [jobTitle, setJobTitle] = useState("");
  const [company, setCompany] = useState("");
  const [systemMessage, setSystemMessage] = useState("");

  // Resume state
  const [tailoredLatex, setTailoredLatex] = useState("");
  const [changesSummary, setChangesSummary] = useState("");
  const [sectionsModified, setSectionsModified] = useState<string[]>([]);
  const [keywordsAdded, setKeywordsAdded] = useState<string[]>([]);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Apply state
  const [applicationId, setApplicationId] = useState("");
  const [resumeVersionId, setResumeVersionId] = useState("");
  const [applyTaskId, setApplyTaskId] = useState("");
  const [actionLog, setActionLog] = useState<Array<{ action: string; detail: string }>>([]);
  const [applyError, setApplyError] = useState<string | null>(null);

  // Loading flags
  const [loading, setLoading] = useState(false);

  // PDF preview
  const [previewTab, setPreviewTab] = useState<"pdf" | "latex">("pdf");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [compileError, setCompileError] = useState<string | null>(null);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Compile LaTeX to PDF whenever tailoredLatex changes
  useEffect(() => {
    if (!tailoredLatex) return;
    let cancelled = false;
    const compile = async () => {
      setCompiling(true);
      setCompileError(null);
      try {
        const { data } = await resumesApi.compilePreview(tailoredLatex);
        if (cancelled) return;
        // Revoke old blob URL
        if (pdfUrl) URL.revokeObjectURL(pdfUrl);
        const url = URL.createObjectURL(data);
        setPdfUrl(url);
      } catch {
        if (!cancelled) setCompileError("Failed to compile PDF preview");
      } finally {
        if (!cancelled) setCompiling(false);
      }
    };
    // Debounce slightly so rapid chat updates don't hammer the endpoint
    const timer = setTimeout(compile, 500);
    return () => { cancelled = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tailoredLatex]);

  // Clean up blob URL on unmount
  useEffect(() => {
    return () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Step 1: Start wizard ─────────────────────────────────────── */

  useEffect(() => {
    async function start() {
      try {
        const { data } = await applicationsApi.wizardStart({
          job_listing_id: jobId,
        });
        setWizardId(data.wizard_id);
        setJobTitle(data.job_title);
        setCompany(data.company);
        setSystemMessage(data.message);
        setStep("confirm_tailor");
      } catch {
        toast.error("Failed to start apply wizard");
        router.push("/jobs");
      }
    }
    start();
  }, [jobId, router]);

  /* ── Step 2: Tailor resume ────────────────────────────────────── */

  const handleTailor = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await applicationsApi.wizardTailor(jobId, {
        wizard_id: wizardId,
      });
      setTailoredLatex(data.tailored_latex);
      setChangesSummary(data.changes_summary || "");
      setSectionsModified(data.sections_modified || []);
      setKeywordsAdded(data.keywords_added || []);
      setSystemMessage(data.message);
      setStep("review_resume");

      // Add system message to chat
      setChatMessages([
        {
          role: "assistant",
          content: data.message,
          latex: data.tailored_latex,
        },
      ]);
    } catch {
      toast.error("Failed to tailor resume");
    } finally {
      setLoading(false);
    }
  }, [jobId, wizardId]);

  /* ── Step 2b: Chat for modifications ──────────────────────────── */

  const handleChatSend = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMsg: ChatMessage = { role: "user", content: chatInput };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);

    try {
      const history = chatMessages
        .filter((m) => m.role !== "system")
        .map((m) => ({ role: m.role, content: m.content }));

      const { data } = await applicationsApi.wizardChat({
        wizard_id: wizardId,
        message: chatInput,
        current_latex: tailoredLatex,
        history,
      });

      if (data.updated_latex) {
        setTailoredLatex(data.updated_latex);
      }

      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.explanation,
          latex: data.updated_latex,
        },
      ]);
    } catch {
      toast.error("AI chat failed");
    } finally {
      setChatLoading(false);
    }
  };

  /* ── Step 3: Approve resume ───────────────────────────────────── */

  const handleApprove = async () => {
    setLoading(true);
    try {
      const { data } = await applicationsApi.wizardApprove({
        wizard_id: wizardId,
        job_listing_id: jobId,
        final_latex: tailoredLatex,
      });
      setApplicationId(data.application_id);
      setResumeVersionId(data.resume_version_id);
      setSystemMessage(data.message);
      setStep("confirm_apply");
    } catch {
      toast.error("Failed to save resume");
    } finally {
      setLoading(false);
    }
  };

  /* ── Step 4: Auto-apply ───────────────────────────────────────── */

  const handleAutoApply = async () => {
    setLoading(true);
    setApplyError(null);
    try {
      const { data } = await applicationsApi.wizardApply({
        application_id: applicationId,
      });
      setApplyTaskId(data.task_id);
      setSystemMessage(data.message);
      setStep("applying");

      // Add a log entry
      setActionLog([
        { action: "queued", detail: "Application task queued" },
      ]);

      // After a brief delay, mark as done (task runs async in backend)
      setTimeout(() => {
        setStep("done");
        setSystemMessage(
          `Application process has been initiated for **${jobTitle}** at **${company}**. ` +
          `The Selenium bot is handling the form submission in the background. ` +
          `Check your Applications page for status updates.`
        );
      }, 3000);
    } catch {
      toast.error("Failed to start auto-apply");
      setApplyError("Could not start the application process");
    } finally {
      setLoading(false);
    }
  };

  /* ── Renderers ────────────────────────────────────────────────── */

  const currentStepIndex = STEPS.findIndex((s) => s.id === step);

  const renderStepIndicator = () => (
    <div className="flex items-center gap-1 mb-6">
      {STEPS.map((s, i) => {
        const Icon = s.icon;
        const isActive = s.id === step;
        const isCompleted = i < currentStepIndex;
        return (
          <div key={s.id} className="flex items-center">
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                isActive
                  ? "bg-brand-600 text-white"
                  : isCompleted
                  ? "bg-green-600 text-white"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {s.label}
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`h-px w-6 mx-1 ${
                  i < currentStepIndex ? "bg-green-500" : "bg-[var(--border)]"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );

  const renderMarkdown = (text: string) => {
    // Simple markdown-like rendering for bold text
    return text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        <span key={i}>{part}</span>
      )
    );
  };

  /* ── Step Renders ─────────────────────────────────────────────── */

  const renderConfirmTailor = () => (
    <div className="max-w-2xl mx-auto">
      <div className="card">
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-brand-100 p-3 dark:bg-brand-900">
            <FiZap className="h-6 w-6 text-brand-600" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-bold mb-2">Ready to apply?</h2>
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {renderMarkdown(systemMessage)}
            </p>
          </div>
        </div>
        <div className="flex gap-3 mt-6 justify-end">
          <button
            onClick={() => router.push("/jobs")}
            className="btn-secondary"
          >
            <FiArrowLeft className="h-4 w-4 mr-1" /> Back to Jobs
          </button>
          <button
            onClick={handleTailor}
            disabled={loading}
            className="btn-primary flex items-center gap-2"
          >
            {loading ? (
              <>
                <FiLoader className="h-4 w-4 animate-spin" /> Tailoring...
              </>
            ) : (
              <>
                <FiCheck className="h-4 w-4" /> Yes, Tailor My Resume
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderReviewResume = () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[calc(100vh-220px)]">
      {/* Left: Resume Preview */}
      <div className="card flex flex-col overflow-hidden">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FiFileText className="h-4 w-4" /> Tailored Resume
          </h3>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-[var(--border)] overflow-hidden text-[10px] font-medium">
              <button
                onClick={() => setPreviewTab("pdf")}
                className={`px-3 py-1 transition-colors ${
                  previewTab === "pdf"
                    ? "bg-brand-600 text-white"
                    : "bg-[var(--card)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                PDF Preview
              </button>
              <button
                onClick={() => setPreviewTab("latex")}
                className={`px-3 py-1 transition-colors ${
                  previewTab === "latex"
                    ? "bg-brand-600 text-white"
                    : "bg-[var(--card)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                LaTeX Source
              </button>
            </div>
            <div className="flex gap-1 flex-wrap">
              {sectionsModified.map((s) => (
                <span key={s} className="badge badge-blue text-[9px]">
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>
        {changesSummary && (
          <div className="mb-3 p-2 bg-green-50 dark:bg-green-900/20 rounded text-xs text-green-700 dark:text-green-300">
            {changesSummary}
          </div>
        )}
        {keywordsAdded.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-1">
            <span className="text-[10px] text-[var(--muted-foreground)]">
              Keywords added:
            </span>
            {keywordsAdded.map((k) => (
              <span key={k} className="badge badge-green text-[9px]">
                {k}
              </span>
            ))}
          </div>
        )}
        {previewTab === "pdf" ? (
          <div className="flex-1 overflow-hidden rounded bg-[var(--muted)] relative min-h-0">
            {compiling && (
              <div className="absolute inset-0 flex items-center justify-center bg-[var(--card)]/80 z-10">
                <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                  <FiLoader className="h-5 w-5 animate-spin text-brand-600" />
                  Compiling PDF...
                </div>
              </div>
            )}
            {compileError && !compiling && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center p-4">
                  <FiAlertCircle className="h-8 w-8 text-amber-500 mx-auto mb-2" />
                  <p className="text-sm text-[var(--muted-foreground)]">{compileError}</p>
                  <button
                    onClick={() => setPreviewTab("latex")}
                    className="mt-2 text-xs text-brand-600 hover:underline"
                  >
                    View LaTeX source instead
                  </button>
                </div>
              </div>
            )}
            {pdfUrl && !compileError && (
              <iframe
                src={pdfUrl}
                className="w-full h-full border-0 rounded"
                title="Resume PDF Preview"
              />
            )}
          </div>
        ) : (
          <pre className="flex-1 overflow-auto bg-[var(--muted)] rounded p-3 text-xs font-mono whitespace-pre-wrap">
            {tailoredLatex}
          </pre>
        )}
      </div>

      {/* Right: Chat Interface */}
      <div className="card flex flex-col overflow-hidden">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <FiMessageCircle className="h-4 w-4" /> Refine Your Resume
        </h3>

        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
          {chatMessages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                  msg.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-[var(--muted)] text-[var(--foreground)]"
                }`}
              >
                {renderMarkdown(msg.content)}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex justify-start">
              <div className="bg-[var(--muted)] rounded-xl px-4 py-2.5 text-sm flex items-center gap-2">
                <FiLoader className="h-4 w-4 animate-spin" /> Thinking...
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Chat input */}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Ask for changes... (e.g. 'Emphasize my Python experience')"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleChatSend()}
            className="input flex-1"
            disabled={chatLoading}
          />
          <button
            onClick={handleChatSend}
            disabled={chatLoading || !chatInput.trim()}
            className="btn-secondary px-3"
          >
            <FiSend className="h-4 w-4" />
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 mt-4 justify-end border-t border-[var(--border)] pt-3">
          <button
            onClick={() => {
              setStep("confirm_tailor");
              setSystemMessage(
                `Would you like me to start over and re-tailor your resume for **${jobTitle}** at **${company}**?`
              );
            }}
            className="btn-secondary text-sm"
          >
            Start Over
          </button>
          <button
            onClick={handleApprove}
            disabled={loading}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            {loading ? (
              <>
                <FiLoader className="h-4 w-4 animate-spin" /> Saving...
              </>
            ) : (
              <>
                <FiCheck className="h-4 w-4" /> Use This Resume & Continue
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderConfirmApply = () => (
    <div className="max-w-2xl mx-auto">
      <div className="card">
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-green-100 p-3 dark:bg-green-900">
            <FiCheck className="h-6 w-6 text-green-600" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-bold mb-2">Resume Saved & Linked</h2>
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {renderMarkdown(systemMessage)}
            </p>
            <div className="mt-3 p-3 bg-[var(--muted)] rounded-lg text-xs space-y-1">
              <p>
                <strong>Application ID:</strong> {applicationId.slice(0, 8)}...
              </p>
              <p>
                <strong>Resume Version:</strong> {resumeVersionId.slice(0, 8)}...
              </p>
            </div>
          </div>
        </div>
        <div className="flex gap-3 mt-6 justify-end">
          <button
            onClick={() => router.push("/applications")}
            className="btn-secondary"
          >
            Skip Auto-Apply
          </button>
          <button
            onClick={handleAutoApply}
            disabled={loading}
            className="btn-primary flex items-center gap-2"
          >
            {loading ? (
              <>
                <FiLoader className="h-4 w-4 animate-spin" /> Starting...
              </>
            ) : (
              <>
                <FiPlay className="h-4 w-4" /> Yes, Apply Automatically
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderApplying = () => (
    <div className="max-w-2xl mx-auto">
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <FiLoader className="h-6 w-6 animate-spin text-brand-600" />
          <h2 className="text-lg font-bold">Applying...</h2>
        </div>
        <p className="text-sm text-[var(--muted-foreground)] mb-4">
          {renderMarkdown(systemMessage)}
        </p>
        <div className="bg-[var(--muted)] rounded-lg p-4 space-y-2">
          {actionLog.map((entry, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-xs"
            >
              <FiCheckCircle className="h-3.5 w-3.5 text-green-500 mt-0.5 shrink-0" />
              <span>
                <strong className="text-[var(--foreground)]">{entry.action}:</strong>{" "}
                {entry.detail}
              </span>
            </div>
          ))}
          <div className="flex items-center gap-2 text-xs text-brand-600">
            <FiLoader className="h-3.5 w-3.5 animate-spin" />
            <span>Processing...</span>
          </div>
        </div>
      </div>
    </div>
  );

  const renderDone = () => (
    <div className="max-w-2xl mx-auto">
      <div className="card">
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-green-100 p-3 dark:bg-green-900">
            <FiCheckCircle className="h-6 w-6 text-green-600" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-bold mb-2">Application Submitted!</h2>
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {renderMarkdown(systemMessage)}
            </p>
            {applyError && (
              <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
                <FiAlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                {applyError}
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-3 mt-6 justify-end">
          <button
            onClick={() => router.push("/jobs")}
            className="btn-secondary"
          >
            Back to Jobs
          </button>
          <button
            onClick={() => router.push("/applications")}
            className="btn-primary"
          >
            View Applications
          </button>
        </div>
      </div>
    </div>
  );

  /* ── Main Render ──────────────────────────────────────────────── */

  if (step === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">
            Apply: {jobTitle}
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            {company} — Guided Application Wizard
          </p>
        </div>
        <button
          onClick={() => router.push("/jobs")}
          className="btn-secondary flex items-center gap-1 text-sm"
        >
          <FiArrowLeft className="h-4 w-4" /> Cancel
        </button>
      </div>

      {/* Step indicator */}
      {renderStepIndicator()}

      {/* Step content */}
      {step === "confirm_tailor" && renderConfirmTailor()}
      {step === "review_resume" && renderReviewResume()}
      {step === "confirm_apply" && renderConfirmApply()}
      {step === "applying" && renderApplying()}
      {step === "done" && renderDone()}
    </div>
  );
}
