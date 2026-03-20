"use client";

import { useEffect, useState, useCallback } from "react";
import { FiSearch, FiUserPlus, FiMessageSquare, FiLinkedin, FiSend, FiX, FiLoader, FiTrash2 } from "react-icons/fi";
import { recruitersApi, agentsApi } from "@/lib/api";
import { formatDate, capitalize } from "@/lib/utils";
import toast from "react-hot-toast";

interface Recruiter {
  id: string;
  name: string;
  title: string;
  company: string;
  linkedin_url: string;
  connection_status: string;
  last_contacted: string | null;
}

export default function RecruitersPage() {
  const [recruiters, setRecruiters] = useState<Recruiter[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState("");
  const [findCompany, setFindCompany] = useState("");
  const [findRole, setFindRole] = useState("");
  const [messageModal, setMessageModal] = useState<{ recruiterId: string; name: string } | null>(null);
  const [generatedMessage, setGeneratedMessage] = useState("");
  const [generatingMsg, setGeneratingMsg] = useState(false);

  const loadRecruiters = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await recruitersApi.list({ limit: 100 });
      setRecruiters(data.recruiters ?? []);
    } catch {
      toast.error("Failed to load recruiters");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRecruiters();
  }, [loadRecruiters]);

  const handleFind = async () => {
    if (!findCompany.trim()) {
      toast.error("Enter a company name");
      return;
    }
    setSearching(true);
    setSearchStatus(`Searching LinkedIn for recruiters at ${findCompany}...`);
    setRecruiters([]);  // Clear previous results immediately
    try {
      const { data } = await recruitersApi.find({
        company: findCompany,
        role: findRole || undefined,
      });
      if (data.source === "linkedin" && data.total > 0) {
        toast.success(`Found ${data.total} recruiters from LinkedIn`);
      } else if (data.source === "none") {
        toast.error("No LinkedIn credentials saved. Go to Settings → Credentials to add your LinkedIn login.");
      } else if (data.total === 0) {
        toast.error("No recruiters found on LinkedIn. Try a different company name or role.");
      } else {
        toast.success(`Found ${data.total} recruiters`);
      }
      setFindCompany("");
      setFindRole("");
      // Show only the recruiters returned by this search (already persisted)
      if (data.recruiters && data.recruiters.length > 0) {
        setRecruiters(data.recruiters);
      } else {
        loadRecruiters();
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to search for recruiters";
      toast.error(msg);
    } finally {
      setSearching(false);
      setSearchStatus("");
    }
  };

  const handleOutreach = async (id: string, type: string) => {
    try {
      await recruitersApi.sendOutreach(id, { message_type: type });
      toast.success("Outreach queued");
      loadRecruiters();
    } catch {
      toast.error("Failed to send outreach");
    }
  };

  const handleGenerateMessage = async (recruiterId: string, name: string) => {
    setMessageModal({ recruiterId, name });
    setGeneratedMessage("");
    setGeneratingMsg(true);
    try {
      const { data } = await recruitersApi.generateMessage({
        recruiter_id: recruiterId,
        message_type: "connection_request",
      });
      setGeneratedMessage(data.message || data.generated_message || "");
    } catch {
      toast.error("Failed to generate message");
      setMessageModal(null);
    } finally {
      setGeneratingMsg(false);
    }
  };

  const handleSendGenerated = async () => {
    if (!messageModal) return;
    try {
      await recruitersApi.sendOutreach(messageModal.recruiterId, {
        message_type: "connection_request",
        custom_message: generatedMessage,
      });
      toast.success("Message sent!");
      setMessageModal(null);
      loadRecruiters();
    } catch {
      toast.error("Failed to send message");
    }
  };

  const handleDeleteRecruiter = async (id: string) => {
    if (!confirm("Move this recruiter to trash?")) return;
    try {
      await recruitersApi.delete(id);
      toast.success("Moved to trash");
      loadRecruiters();
    } catch {
      toast.error("Failed to delete recruiter");
    }
  };

  const connectionBadge: Record<string, string> = {
    not_connected: "badge-gray",
    pending: "badge-yellow",
    connected: "badge-green",
    ignored: "badge-red",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Recruiters</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Find and connect with recruiters at target companies
        </p>
      </div>

      {/* Find recruiters panel */}
      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">
          <FiSearch className="mr-1 inline h-4 w-4" /> Find Recruiters
        </h3>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Company name"
            value={findCompany}
            onChange={(e) => setFindCompany(e.target.value)}
            className="input max-w-xs"
            disabled={searching}
          />
          <input
            type="text"
            placeholder="Role (optional)"
            value={findRole}
            onChange={(e) => setFindRole(e.target.value)}
            className="input max-w-xs"
            disabled={searching}
          />
          <button onClick={handleFind} className="btn-primary" disabled={searching}>
            {searching ? (
              <span className="flex items-center gap-2">
                <FiLoader className="h-4 w-4 animate-spin" /> Searching...
              </span>
            ) : (
              "Search"
            )}
          </button>
        </div>
        {searching && (
          <div className="mt-3 flex items-center gap-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 px-4 py-3 border border-blue-200 dark:border-blue-800">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">{searchStatus}</p>
              <p className="text-xs text-blue-500 dark:text-blue-500 mt-0.5">
                This may take 15-30 seconds while we search LinkedIn
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Recruiter cards */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        </div>
      ) : recruiters.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-[var(--muted-foreground)]">
            No recruiters found yet. Search for recruiters at your target companies above.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {recruiters.map((rec) => (
            <div key={rec.id} className="card space-y-3">
              <div>
                <h3 className="font-semibold text-[var(--foreground)]">{rec.name}</h3>
                <p className="text-sm text-[var(--muted-foreground)]">{rec.title}</p>
                <p className="text-sm text-[var(--muted-foreground)]">{rec.company}</p>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`badge ${
                    connectionBadge[rec.connection_status] || "badge-gray"
                  }`}
                >
                  {capitalize(rec.connection_status.replace("_", " "))}
                </span>
                {rec.last_contacted && (
                  <span className="text-[10px] text-[var(--muted-foreground)]">
                    Last: {formatDate(rec.last_contacted)}
                  </span>
                )}
              </div>
              <div className="flex gap-2 flex-wrap">
                {rec.connection_status === "not_connected" && (
                  <>
                    <button
                      onClick={() => handleOutreach(rec.id, "connection_request")}
                      className="btn-primary flex items-center gap-1 text-xs"
                    >
                      <FiUserPlus className="h-3.5 w-3.5" /> Connect
                    </button>
                    <button
                      onClick={() => handleGenerateMessage(rec.id, rec.name)}
                      className="btn-secondary flex items-center gap-1 text-xs"
                    >
                      <FiSend className="h-3.5 w-3.5" /> AI Message
                    </button>
                  </>
                )}
                {rec.connection_status === "connected" && (
                  <>
                    <button
                      onClick={() => handleOutreach(rec.id, "followup")}
                      className="btn-secondary flex items-center gap-1 text-xs"
                    >
                      <FiMessageSquare className="h-3.5 w-3.5" /> Message
                    </button>
                    <button
                      onClick={() => handleGenerateMessage(rec.id, rec.name)}
                      className="btn-secondary flex items-center gap-1 text-xs"
                    >
                      <FiSend className="h-3.5 w-3.5" /> AI Message
                    </button>
                  </>
                )}
                <a
                  href={rec.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary flex items-center gap-1 text-xs"
                >
                  <FiLinkedin className="h-3.5 w-3.5" /> Profile
                </a>
                <button
                  onClick={() => handleDeleteRecruiter(rec.id)}
                  className="ml-auto text-[var(--muted-foreground)] hover:text-red-500 transition-colors p-1"
                  title="Move to trash"
                >
                  <FiTrash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Message Preview Modal */}
      {messageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--card)] rounded-xl shadow-2xl w-full max-w-lg p-6 relative">
            <button
              onClick={() => setMessageModal(null)}
              className="absolute top-3 right-3 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              <FiX className="h-5 w-5" />
            </button>
            <h2 className="text-lg font-bold mb-1">AI-Generated Message</h2>
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              For {messageModal.name}
            </p>
            {generatingMsg ? (
              <div className="flex items-center justify-center py-8 gap-2 text-sm text-[var(--muted-foreground)]">
                <FiLoader className="h-4 w-4 animate-spin" /> Generating personalized message...
              </div>
            ) : (
              <>
                <textarea
                  value={generatedMessage}
                  onChange={(e) => setGeneratedMessage(e.target.value)}
                  rows={6}
                  className="input w-full font-mono text-sm"
                />
                <p className="text-xs text-[var(--muted-foreground)] mt-2">
                  Edit the message above before sending, or send as-is.
                </p>
                <div className="flex gap-3 mt-4 justify-end">
                  <button onClick={() => setMessageModal(null)} className="btn-secondary">
                    Cancel
                  </button>
                  <button onClick={handleSendGenerated} className="btn-primary flex items-center gap-1">
                    <FiSend className="h-4 w-4" /> Send
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
