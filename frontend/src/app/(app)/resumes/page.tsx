"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  FiPlus,
  FiEdit3,
  FiTrash2,
  FiDownload,
  FiStar,
  FiCode,
  FiEye,
  FiColumns,
  FiLoader,
  FiAlertCircle,
  FiSave,
  FiFileText,
  FiChevronLeft,
  FiChevronRight,
  FiMessageSquare,
  FiRotateCcw,
  FiCpu,
  FiSend,
  FiX,
} from "react-icons/fi";
import { resumesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import dynamic from "next/dynamic";

// Lazy-load Monaco editor
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((m) => m.default),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">
        Loading editor...
      </div>
    ),
  }
);

interface Resume {
  id: string;
  name: string;
  is_master: boolean;
  version_number: number;
  latex_source: string;
  pdf_s3_key: string | null;
  compilation_status: string;
  parsed_sections: string | null;
  created_at: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

type ViewMode = "split" | "editor" | "preview";

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selected, setSelected] = useState<Resume | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("split");

  // PDF preview state
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [compileErrors, setCompileErrors] = useState<string[]>([]);
  const prevPdfUrl = useRef<string | null>(null);

  // Sidebar state
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const [sidebarHover, setSidebarHover] = useState(false);
  const sidebarOpen = sidebarPinned || sidebarHover;

  // AI Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Parse state
  const [parsing, setParsing] = useState(false);
  const [parsedSections, setParsedSections] = useState<Record<string, string> | null>(null);

  // Rollback state
  const [rollingBack, setRollingBack] = useState<string | null>(null);

  const loadResumes = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await resumesApi.list();
      setResumes(data.resumes ?? data ?? []);
    } catch {
      toast.error("Failed to load resumes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadResumes();
  }, [loadResumes]);

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (prevPdfUrl.current) URL.revokeObjectURL(prevPdfUrl.current);
    };
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const selectResume = (resume: Resume) => {
    setSelected(resume);
    setEditorContent(resume.latex_source);
    setPdfUrl(null);
    setCompileErrors([]);
    setParsedSections(null);
    setChatMessages([]);
    // Auto-compile to show PDF preview immediately
    autoCompile(resume.latex_source);
  };

  const autoCompile = async (latex: string) => {
    if (!latex.trim()) return;
    setCompiling(true);
    setCompileErrors([]);
    try {
      const { data } = await resumesApi.compilePreview(latex);
      if (prevPdfUrl.current) URL.revokeObjectURL(prevPdfUrl.current);
      const url = URL.createObjectURL(data);
      prevPdfUrl.current = url;
      setPdfUrl(url);
    } catch {
      // Silent fail on auto-compile — user can always manually recompile
    } finally {
      setCompiling(false);
    }
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await resumesApi.update(selected.id, { latex_source: editorContent });
      toast.success("Resume saved");
      loadResumes();
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleCompilePreview = async () => {
    if (!editorContent.trim()) return;
    setCompiling(true);
    setCompileErrors([]);
    try {
      const { data } = await resumesApi.compilePreview(editorContent);
      // Revoke previous URL to free memory
      if (prevPdfUrl.current) URL.revokeObjectURL(prevPdfUrl.current);
      const url = URL.createObjectURL(data);
      prevPdfUrl.current = url;
      setPdfUrl(url);
    } catch (err: unknown) {
      // Try to extract error details from blob response
      const error = err as { response?: { data?: Blob } };
      if (error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const json = JSON.parse(text);
          const detail = json.detail;
          if (detail?.errors) {
            setCompileErrors(detail.errors);
          } else if (typeof detail === "string") {
            setCompileErrors([detail]);
          } else {
            setCompileErrors(["Compilation failed"]);
          }
        } catch {
          setCompileErrors(["Compilation failed"]);
        }
      } else {
        setCompileErrors(["Compilation failed — server error"]);
      }
    } finally {
      setCompiling(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!pdfUrl || !selected) return;
    const a = document.createElement("a");
    a.href = pdfUrl;
    a.download = `${selected.name}.pdf`;
    a.click();
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await resumesApi.create({
        name: newName,
        latex_source: DEFAULT_LATEX,
        is_master: resumes.length === 0,
      });
      toast.success("Resume created");
      setShowNew(false);
      setNewName("");
      loadResumes();
    } catch {
      toast.error("Failed to create resume");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this resume version?")) return;
    try {
      await resumesApi.delete(id);
      toast.success("Deleted");
      if (selected?.id === id) {
        setSelected(null);
        setPdfUrl(null);
      }
      loadResumes();
    } catch {
      toast.error("Failed to delete");
    }
  };

  // ── AI Chat ──
  const handleChatSend = async () => {
    if (!selected || !chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setChatLoading(true);
    try {
      const { data } = await resumesApi.chat({
        resume_id: selected.id,
        message: userMsg,
      });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.explanation || data.message || "Done." },
      ]);
      if (data.updated_latex) {
        setEditorContent(data.updated_latex);
        toast.success("LaTeX updated by AI");
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // ── Parse resume sections ──
  const handleParse = async () => {
    if (!selected) return;
    setParsing(true);
    try {
      const { data } = await resumesApi.parse(selected.id);
      setParsedSections(data.sections || {});
      toast.success("Resume parsed into sections");
    } catch {
      toast.error("Failed to parse resume");
    } finally {
      setParsing(false);
    }
  };

  // ── Rollback to a version ──
  const handleRollback = async (targetId: string) => {
    if (!confirm("Rollback to this version? A new version will be created from it.")) return;
    setRollingBack(targetId);
    try {
      await resumesApi.rollback({ target_version_id: targetId });
      toast.success("Rolled back successfully");
      await loadResumes();
    } catch {
      toast.error("Failed to rollback");
    } finally {
      setRollingBack(null);
    }
  };

  const showEditor = viewMode === "split" || viewMode === "editor";
  const showPreview = viewMode === "split" || viewMode === "preview";

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-0 relative">
      {/* ─── Sidebar: collapsible resume list ─── */}
      <div
        className={`shrink-0 border-r border-[var(--border)] bg-[var(--card)] flex flex-col transition-all duration-300 ease-in-out z-20 ${
          sidebarOpen ? "w-60" : "w-10"
        } ${!sidebarPinned && sidebarHover ? "absolute inset-y-0 left-0 shadow-2xl" : "relative"}`}
        onMouseEnter={() => setSidebarHover(true)}
        onMouseLeave={() => setSidebarHover(false)}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-2 py-2.5 border-b border-[var(--border)] min-h-[44px]">
          {sidebarOpen ? (
            <>
              <h1 className="text-sm font-bold text-[var(--foreground)] pl-1 whitespace-nowrap">Resumes</h1>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setShowNew(true)}
                  className="btn-primary flex items-center gap-1 text-[10px] px-1.5 py-0.5"
                  title="New Resume"
                >
                  <FiPlus className="h-3 w-3" />
                </button>
                <button
                  onClick={() => setSidebarPinned(!sidebarPinned)}
                  className="p-1 rounded text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]/50 transition-colors"
                  title={sidebarPinned ? "Unpin sidebar" : "Pin sidebar"}
                >
                  {sidebarPinned ? <FiChevronLeft className="h-3.5 w-3.5" /> : <FiChevronRight className="h-3.5 w-3.5" />}
                </button>
              </div>
            </>
          ) : (
            <button
              className="w-full flex justify-center p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
              title="Expand sidebar"
            >
              <FiFileText className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Content — only visible when open */}
        {sidebarOpen && (
          <>
            {showNew && (
              <div className="mx-2 mt-2 p-2 rounded-lg border border-[var(--border)] bg-[var(--background)] space-y-2">
                <input
                  type="text"
                  placeholder="Resume name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  className="input text-sm w-full"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button onClick={handleCreate} className="btn-primary text-xs px-2 py-1">
                    Create
                  </button>
                  <button
                    onClick={() => {
                      setShowNew(false);
                      setNewName("");
                    }}
                    className="btn-secondary text-xs px-2 py-1"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
              {loading ? (
                <div className="flex justify-center py-8">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
                </div>
              ) : resumes.length === 0 ? (
                <p className="text-center text-xs text-[var(--muted-foreground)] py-8">
                  No resumes yet.
                </p>
              ) : (
                resumes.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => { selectResume(r); if (!sidebarPinned) setSidebarHover(false); }}
                    className={`rounded-lg px-3 py-2 cursor-pointer transition-all text-sm border ${
                      selected?.id === r.id
                        ? "border-brand-500 bg-brand-500/10"
                        : "border-transparent hover:bg-[var(--muted)]/50"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      {r.is_master && <FiStar className="h-3 w-3 text-yellow-500 shrink-0" />}
                      <span className="font-medium text-[var(--foreground)] truncate text-xs">
                        {r.name}
                      </span>
                      <span className="ml-auto text-[10px] text-[var(--muted-foreground)] shrink-0">
                        v{r.version_number}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="text-[10px] text-[var(--muted-foreground)]">
                        {formatDate(r.created_at)}
                      </span>
                      <div className="flex items-center gap-1">
                        {selected?.id !== r.id && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRollback(r.id);
                            }}
                            disabled={rollingBack === r.id}
                            className="text-[var(--muted-foreground)] hover:text-blue-500 transition-colors"
                            title="Rollback to this version"
                          >
                            {rollingBack === r.id ? (
                              <FiLoader className="h-3 w-3 animate-spin" />
                            ) : (
                              <FiRotateCcw className="h-3 w-3" />
                            )}
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(r.id);
                          }}
                          className="text-[var(--muted-foreground)] hover:text-red-500 transition-colors"
                        >
                          <FiTrash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {/* Collapsed state: show icons for each resume */}
        {!sidebarOpen && (
          <div className="flex-1 overflow-y-auto py-2 space-y-1 flex flex-col items-center">
            {resumes.slice(0, 10).map((r) => (
              <button
                key={r.id}
                onClick={() => selectResume(r)}
                className={`w-7 h-7 rounded flex items-center justify-center text-[10px] font-bold transition-colors ${
                  selected?.id === r.id
                    ? "bg-brand-500 text-white"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50"
                }`}
                title={r.name}
              >
                {r.name.charAt(0).toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Spacer when sidebar is unpinned overlay to prevent content shift */}
      {!sidebarPinned && (
        <div className="w-10 shrink-0" />
      )}

      {/* ─── Main content: Editor + Preview ─── */}
      {selected ? (
        <div className="flex-1 flex flex-col min-w-0">
          {/* Toolbar */}
          <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--card)] px-4 py-2">
            <div className="flex items-center gap-3">
              <h2 className="font-semibold text-sm text-[var(--foreground)] flex items-center gap-1.5">
                <FiEdit3 className="h-3.5 w-3.5" />
                {selected.name}
              </h2>
              {selected.is_master && (
                <span className="text-[10px] bg-yellow-500/20 text-yellow-600 px-1.5 py-0.5 rounded font-medium">
                  MASTER
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* View mode toggle */}
              <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
                <button
                  onClick={() => setViewMode("editor")}
                  className={`px-2 py-1 text-xs flex items-center gap-1 transition-colors ${
                    viewMode === "editor"
                      ? "bg-brand-500 text-white"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50"
                  }`}
                  title="Code Editor"
                >
                  <FiCode className="h-3 w-3" />
                </button>
                <button
                  onClick={() => setViewMode("split")}
                  className={`px-2 py-1 text-xs flex items-center gap-1 border-x border-[var(--border)] transition-colors ${
                    viewMode === "split"
                      ? "bg-brand-500 text-white"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50"
                  }`}
                  title="Split View"
                >
                  <FiColumns className="h-3 w-3" />
                </button>
                <button
                  onClick={() => setViewMode("preview")}
                  className={`px-2 py-1 text-xs flex items-center gap-1 transition-colors ${
                    viewMode === "preview"
                      ? "bg-brand-500 text-white"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50"
                  }`}
                  title="PDF Preview"
                >
                  <FiEye className="h-3 w-3" />
                </button>
              </div>

              {/* Parse button */}
              <button
                onClick={handleParse}
                disabled={parsing}
                className="btn-secondary flex items-center gap-1 text-xs"
                title="AI Parse — extract resume sections"
              >
                <FiCpu className="h-3.5 w-3.5" />
                {parsing ? "Parsing..." : "Parse"}
              </button>

              {/* AI Chat toggle */}
              <button
                onClick={() => setChatOpen(!chatOpen)}
                className={`flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                  chatOpen
                    ? "bg-purple-600 text-white"
                    : "bg-purple-600/20 text-purple-400 hover:bg-purple-600/30"
                }`}
                title="Toggle AI Chat"
              >
                <FiMessageSquare className="h-3.5 w-3.5" />
                AI Chat
              </button>

              {/* Recompile button */}
              <button
                onClick={handleCompilePreview}
                disabled={compiling}
                className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                  compiling
                    ? "bg-green-600/50 text-white cursor-wait"
                    : "bg-green-600 hover:bg-green-700 text-white"
                }`}
              >
                {compiling ? (
                  <FiLoader className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FiEye className="h-3.5 w-3.5" />
                )}
                {compiling ? "Compiling..." : "Recompile"}
              </button>

              {/* Download */}
              {pdfUrl && (
                <button
                  onClick={handleDownloadPdf}
                  className="btn-secondary flex items-center gap-1 text-xs"
                  title="Download PDF"
                >
                  <FiDownload className="h-3.5 w-3.5" />
                </button>
              )}

              {/* Save */}
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary flex items-center gap-1 text-xs"
              >
                <FiSave className="h-3.5 w-3.5" />
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>

          {/* Editor + Preview + Chat panels */}
          <div className="flex-1 flex min-h-0">
            {/* Code Editor Panel */}
            {showEditor && (
              <div
                className={`flex flex-col min-w-0 ${
                  showPreview && !chatOpen ? "w-1/2 border-r border-[var(--border)]"
                  : showPreview && chatOpen ? "w-1/3 border-r border-[var(--border)]"
                  : chatOpen ? "flex-1 border-r border-[var(--border)]"
                  : "w-full"
                }`}
              >
                {/* Editor tab bar */}
                <div className="flex items-center bg-[#1e1e1e] px-3 py-1.5 border-b border-[#333]">
                  <span className="text-xs text-gray-400 flex items-center gap-1.5">
                    <FiCode className="h-3 w-3" />
                    main.tex
                  </span>
                  <span className="ml-2 text-[10px] text-gray-500">
                    &mdash; Editing
                  </span>
                </div>
                <div className="flex-1">
                  <MonacoEditor
                    height="100%"
                    language="latex"
                    theme="vs-dark"
                    value={editorContent}
                    onChange={(val) => setEditorContent(val || "")}
                    options={{
                      fontSize: 13,
                      fontFamily: "JetBrains Mono, Fira Code, Consolas, monospace",
                      minimap: { enabled: false },
                      wordWrap: "on",
                      lineNumbers: "on",
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      renderLineHighlight: "gutter",
                      padding: { top: 8 },
                      suggest: { showWords: false },
                    }}
                  />
                </div>
              </div>
            )}

            {/* PDF Preview Panel */}
            {showPreview && (
              <div
                className={`flex flex-col bg-gray-100 dark:bg-neutral-800 min-w-0 ${
                  showEditor && !chatOpen ? "w-1/2"
                  : showEditor && chatOpen ? "w-1/3"
                  : chatOpen ? "flex-1"
                  : "w-full"
                }`}
              >
                {/* Preview tab bar */}
                <div className="flex items-center justify-between bg-gray-200 dark:bg-neutral-700 px-3 py-1.5">
                  <span className="text-xs text-gray-600 dark:text-gray-300 flex items-center gap-1.5">
                    <FiEye className="h-3 w-3" />
                    PDF Preview
                  </span>
                  {pdfUrl && (
                    <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">
                      Compiled successfully
                    </span>
                  )}
                </div>

                <div className="flex-1 overflow-auto">
                  {compiling ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3">
                      <FiLoader className="h-8 w-8 animate-spin text-brand-500" />
                      <p className="text-sm text-[var(--muted-foreground)]">
                        Compiling LaTeX...
                      </p>
                    </div>
                  ) : compileErrors.length > 0 ? (
                    <div className="p-4 space-y-3">
                      <div className="flex items-center gap-2 text-red-500">
                        <FiAlertCircle className="h-5 w-5 shrink-0" />
                        <span className="font-semibold text-sm">Compilation Errors</span>
                      </div>
                      <div className="space-y-2">
                        {compileErrors.map((err, i) => (
                          <pre
                            key={i}
                            className="text-xs bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-lg p-3 whitespace-pre-wrap font-mono overflow-x-auto"
                          >
                            {err}
                          </pre>
                        ))}
                      </div>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        Fix the errors in the editor and click Recompile.
                      </p>
                    </div>
                  ) : pdfUrl ? (
                    <iframe
                      src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=1&view=FitH`}
                      className="w-full h-full border-0"
                      title="PDF Preview"
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full gap-3 px-6 text-center">
                      <div className="w-16 h-16 rounded-full bg-gray-200 dark:bg-neutral-600 flex items-center justify-center">
                        <FiEye className="h-8 w-8 text-gray-400 dark:text-gray-500" />
                      </div>
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        No preview yet
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)] max-w-xs">
                        Click the green <strong>Recompile</strong> button to compile
                        your LaTeX and see the PDF preview here.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* AI Chat Panel */}
            {chatOpen && (
              <div className="w-80 shrink-0 border-l border-[var(--border)] bg-[var(--card)] flex flex-col">
                {/* Chat header */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
                  <span className="text-xs font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                    <FiMessageSquare className="h-3.5 w-3.5 text-purple-500" />
                    AI Resume Assistant
                  </span>
                  <button
                    onClick={() => setChatOpen(false)}
                    className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    <FiX className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* Chat messages */}
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {chatMessages.length === 0 && (
                    <div className="text-center py-8">
                      <FiMessageSquare className="h-8 w-8 mx-auto text-purple-500/30 mb-2" />
                      <p className="text-xs text-[var(--muted-foreground)]">
                        Ask the AI to modify your resume. For example:
                      </p>
                      <div className="mt-2 space-y-1">
                        {[
                          "Add a skills section for Python and React",
                          "Make my experience bullets more impactful",
                          "Tailor this for a ML Engineer role",
                        ].map((hint) => (
                          <button
                            key={hint}
                            onClick={() => setChatInput(hint)}
                            className="block w-full text-left text-[10px] text-purple-400 hover:text-purple-300 px-2 py-1 rounded hover:bg-purple-500/10 transition-colors"
                          >
                            &quot;{hint}&quot;
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`text-xs rounded-lg p-2.5 ${
                        msg.role === "user"
                          ? "bg-brand-500/10 text-[var(--foreground)] ml-4"
                          : "bg-purple-500/10 text-[var(--foreground)] mr-4"
                      }`}
                    >
                      <span className="font-semibold text-[10px] block mb-1 opacity-60">
                        {msg.role === "user" ? "You" : "AI"}
                      </span>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                      <FiLoader className="h-3 w-3 animate-spin" />
                      AI is thinking...
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Chat input */}
                <div className="p-2 border-t border-[var(--border)]">
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      placeholder="Ask AI to modify your resume..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleChatSend()}
                      disabled={chatLoading}
                      className="input text-xs flex-1"
                    />
                    <button
                      onClick={handleChatSend}
                      disabled={chatLoading || !chatInput.trim()}
                      className="btn-primary p-1.5"
                    >
                      <FiSend className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Parsed Sections panel (slides in from bottom when parsed) */}
          {parsedSections && (
            <div className="border-t border-[var(--border)] bg-[var(--card)] max-h-48 overflow-y-auto p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-[var(--foreground)]">
                  Parsed Resume Sections
                </h3>
                <button
                  onClick={() => setParsedSections(null)}
                  className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                >
                  <FiX className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(parsedSections).map(([key, val]) => (
                  <div key={key} className="rounded border border-[var(--border)] p-2">
                    <h4 className="text-[10px] font-bold text-brand-500 uppercase mb-1">
                      {key.replace(/_/g, " ")}
                    </h4>
                    <p className="text-[10px] text-[var(--foreground)] line-clamp-3 whitespace-pre-wrap">
                      {val}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-[var(--muted-foreground)]">
          <div className="text-center space-y-2">
            <FiEdit3 className="h-12 w-12 mx-auto opacity-30" />
            <p className="text-sm">Select a resume to edit, or create a new one.</p>
          </div>
        </div>
      )}
    </div>
  );
}

const DEFAULT_LATEX = `\\documentclass[11pt,a4paper]{article}
\\usepackage[margin=0.75in]{geometry}
\\usepackage{enumitem}
\\usepackage{hyperref}
\\usepackage{titlesec}

\\titleformat{\\section}{\\large\\bfseries}{}{0em}{}[\\titlerule]
\\setlength{\\parindent}{0pt}

\\begin{document}

\\begin{center}
  {\\LARGE\\bfseries Your Name} \\\\[4pt]
  \\href{mailto:email@example.com}{email@example.com} \\quad | \\quad
  +1-234-567-8900 \\quad | \\quad
  \\href{https://linkedin.com/in/yourprofile}{LinkedIn} \\quad | \\quad
  \\href{https://github.com/yourprofile}{GitHub}
\\end{center}

\\section{Summary}
Experienced software engineer with expertise in building scalable systems.

\\section{Experience}
\\textbf{Software Engineer} \\hfill Company Name \\\\
\\textit{Jan 2022 -- Present} \\hfill City, State
\\begin{itemize}[leftmargin=*,nosep]
  \\item Built and maintained microservices handling 10M+ requests/day
  \\item Led migration from monolith to event-driven architecture
\\end{itemize}

\\section{Education}
\\textbf{B.S. Computer Science} \\hfill University Name \\\\
\\textit{2018 -- 2022} \\hfill City, State

\\section{Skills}
Python, TypeScript, React, FastAPI, PostgreSQL, Docker, AWS, Kubernetes

\\end{document}`;
