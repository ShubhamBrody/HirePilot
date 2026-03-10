"use client";

import { useEffect, useState, useCallback } from "react";
import { FiSearch, FiUserPlus, FiMessageSquare, FiLinkedin } from "react-icons/fi";
import { recruitersApi } from "@/lib/api";
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
  const [findCompany, setFindCompany] = useState("");
  const [findRole, setFindRole] = useState("");

  const loadRecruiters = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await recruitersApi.list({ limit: 100 });
      setRecruiters(data.items || []);
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
    try {
      await recruitersApi.find({
        company: findCompany,
        role: findRole || undefined,
      });
      toast.success("Recruiter search started");
      setFindCompany("");
      setFindRole("");
    } catch {
      toast.error("Failed to search for recruiters");
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
          />
          <input
            type="text"
            placeholder="Role (optional)"
            value={findRole}
            onChange={(e) => setFindRole(e.target.value)}
            className="input max-w-xs"
          />
          <button onClick={handleFind} className="btn-primary">
            Search
          </button>
        </div>
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
              <div className="flex gap-2">
                {rec.connection_status === "not_connected" && (
                  <button
                    onClick={() => handleOutreach(rec.id, "connection_request")}
                    className="btn-primary flex items-center gap-1 text-xs"
                  >
                    <FiUserPlus className="h-3.5 w-3.5" /> Connect
                  </button>
                )}
                {rec.connection_status === "connected" && (
                  <button
                    onClick={() => handleOutreach(rec.id, "followup")}
                    className="btn-secondary flex items-center gap-1 text-xs"
                  >
                    <FiMessageSquare className="h-3.5 w-3.5" /> Message
                  </button>
                )}
                <a
                  href={rec.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary flex items-center gap-1 text-xs"
                >
                  <FiLinkedin className="h-3.5 w-3.5" /> Profile
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
