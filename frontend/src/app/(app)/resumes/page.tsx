"use client";

import { useEffect, useState, useCallback } from "react";
import { FiPlus, FiEdit3, FiTrash2, FiDownload, FiStar, FiZap } from "react-icons/fi";
import { resumesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import dynamic from "next/dynamic";

// Lazy-load Monaco editor (heavy)
const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => <div className="flex h-96 items-center justify-center text-sm text-[var(--muted-foreground)]">Loading editor...</div>,
});

interface Resume {
  id: string;
  name: string;
  is_master: boolean;
  version_number: number;
  latex_content: string;
  pdf_url: string | null;
  compiled_successfully: boolean | null;
  created_at: string;
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selected, setSelected] = useState<Resume | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");

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

  const selectResume = (resume: Resume) => {
    setSelected(resume);
    setEditorContent(resume.latex_content);
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await resumesApi.update(selected.id, {
        latex_content: editorContent,
      });
      toast.success("Resume saved");
      loadResumes();
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleCompile = async () => {
    if (!selected) return;
    try {
      await resumesApi.compile(selected.id);
      toast.success("Compilation started");
    } catch {
      toast.error("Compilation failed");
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await resumesApi.create({
        name: newName,
        latex_content: DEFAULT_LATEX,
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
      if (selected?.id === id) setSelected(null);
      loadResumes();
    } catch {
      toast.error("Failed to delete");
    }
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4">
      {/* Sidebar - resume list */}
      <div className="w-72 shrink-0 space-y-3 overflow-y-auto">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-[var(--foreground)]">Resumes</h1>
          <button onClick={() => setShowNew(true)} className="btn-primary flex items-center gap-1 text-xs px-2.5 py-1.5">
            <FiPlus className="h-3.5 w-3.5" /> New
          </button>
        </div>

        {showNew && (
          <div className="card space-y-2">
            <input
              type="text"
              placeholder="Resume name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="input text-sm"
            />
            <div className="flex gap-2">
              <button onClick={handleCreate} className="btn-primary text-xs px-2 py-1">Create</button>
              <button onClick={() => setShowNew(false)} className="btn-secondary text-xs px-2 py-1">Cancel</button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          </div>
        ) : (
          resumes.map((r) => (
            <div
              key={r.id}
              onClick={() => selectResume(r)}
              className={`card cursor-pointer transition-all text-sm ${
                selected?.id === r.id ? "ring-2 ring-brand-500" : "hover:shadow-md"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {r.is_master && <FiStar className="h-3.5 w-3.5 text-yellow-500" />}
                  <span className="font-medium text-[var(--foreground)] truncate max-w-[150px]">
                    {r.name}
                  </span>
                </div>
                <span className="text-[10px] text-[var(--muted-foreground)]">v{r.version_number}</span>
              </div>
              <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">
                {formatDate(r.created_at)}
              </p>
              <div className="mt-1 flex gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(r.id); }}
                  className="text-[var(--muted-foreground)] hover:text-red-500 transition-colors"
                >
                  <FiTrash2 className="h-3.5 w-3.5" />
                </button>
                {r.pdf_url && (
                  <a
                    href={r.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-[var(--muted-foreground)] hover:text-brand-500 transition-colors"
                  >
                    <FiDownload className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col card p-0 overflow-hidden">
        {selected ? (
          <>
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <h2 className="font-semibold text-[var(--foreground)]">
                <FiEdit3 className="mr-1.5 inline h-4 w-4" />
                {selected.name}
              </h2>
              <div className="flex gap-2">
                <button onClick={handleCompile} className="btn-secondary flex items-center gap-1 text-xs">
                  <FiZap className="h-3.5 w-3.5" /> Compile PDF
                </button>
                <button onClick={handleSave} disabled={saving} className="btn-primary text-xs">
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
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
                  fontFamily: "JetBrains Mono, Fira Code, monospace",
                  minimap: { enabled: false },
                  wordWrap: "on",
                  lineNumbers: "on",
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                }}
              />
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-[var(--muted-foreground)]">
            Select a resume to edit, or create a new one.
          </div>
        )}
      </div>
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
