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
  created_at: string;
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

  const selectResume = (resume: Resume) => {
    setSelected(resume);
    setEditorContent(resume.latex_source);
    setPdfUrl(null);
    setCompileErrors([]);
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

  const showEditor = viewMode === "split" || viewMode === "editor";
  const showPreview = viewMode === "split" || viewMode === "preview";

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-0">
      {/* ─── Sidebar: resume list ─── */}
      <div className="w-60 shrink-0 border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
        <div className="flex items-center justify-between px-3 py-3 border-b border-[var(--border)]">
          <h1 className="text-base font-bold text-[var(--foreground)]">Resumes</h1>
          <button
            onClick={() => setShowNew(true)}
            className="btn-primary flex items-center gap-1 text-xs px-2 py-1"
          >
            <FiPlus className="h-3 w-3" /> New
          </button>
        </div>

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

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
            </div>
          ) : resumes.length === 0 ? (
            <p className="text-center text-xs text-[var(--muted-foreground)] py-8">
              No resumes yet. Create one to get started.
            </p>
          ) : (
            resumes.map((r) => (
              <div
                key={r.id}
                onClick={() => selectResume(r)}
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
            ))
          )}
        </div>
      </div>

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

          {/* Editor + Preview panels */}
          <div className="flex-1 flex min-h-0">
            {/* Code Editor Panel */}
            {showEditor && (
              <div
                className={`flex flex-col min-w-0 ${
                  showPreview ? "w-1/2 border-r border-[var(--border)]" : "w-full"
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
                  showEditor ? "w-1/2" : "w-full"
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
                      src={pdfUrl}
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
          </div>
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
