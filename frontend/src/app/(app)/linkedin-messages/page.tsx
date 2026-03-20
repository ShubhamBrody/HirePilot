"use client";

import { useEffect, useState, useCallback } from "react";
import {
  FiMessageSquare,
  FiSend,
  FiCheck,
  FiClock,
  FiAlertCircle,
  FiLinkedin,
  FiRefreshCw,
  FiChevronDown,
  FiChevronUp,
  FiWifi,
  FiLoader,
  FiInbox,
} from "react-icons/fi";
import { recruitersApi } from "@/lib/api";
import { formatDate, capitalize } from "@/lib/utils";
import toast from "react-hot-toast";

interface OutreachMessage {
  id: string;
  recruiter_id: string;
  recruiter_name: string;
  recruiter_company: string;
  recruiter_title: string;
  message_type: string;
  subject: string | null;
  body: string;
  ai_generated: boolean;
  status: string;
  sent_at: string | null;
  error_message: string | null;
  created_at: string | null;
}

interface LinkedInConversation {
  sender_name?: string;
  last_message?: string;
  timestamp?: string;
  unread?: boolean;
}

const statusConfig: Record<string, { icon: React.ReactNode; badge: string }> = {
  pending: { icon: <FiClock className="h-4 w-4 text-yellow-500" />, badge: "badge-yellow" },
  sent: { icon: <FiCheck className="h-4 w-4 text-green-500" />, badge: "badge-green" },
  delivered: { icon: <FiCheck className="h-4 w-4 text-green-600" />, badge: "badge-green" },
  failed: { icon: <FiAlertCircle className="h-4 w-4 text-red-500" />, badge: "badge-red" },
  replied: { icon: <FiMessageSquare className="h-4 w-4 text-blue-500" />, badge: "badge-blue" },
};

const typeLabels: Record<string, string> = {
  connection_request: "Connection Request",
  follow_up: "Follow-up",
  followup: "Follow-up",
  inmail: "InMail",
  reply: "Reply",
};

export default function LinkedInMessagesPage() {
  const [tab, setTab] = useState<"inbox" | "outreach">("inbox");
  // Outreach state
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");
  // LinkedIn inbox state
  const [conversations, setConversations] = useState<LinkedInConversation[]>([]);
  const [inboxLoading, setInboxLoading] = useState(false);
  const [inboxMessage, setInboxMessage] = useState<string>("");
  const [connectionStatus, setConnectionStatus] = useState<"unknown" | "testing" | "connected" | "failed" | "challenge">("unknown");
  const [challengeMessage, setChallengeMessage] = useState<string>("");

  const loadOutreach = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await recruitersApi.getAllMessages({ page_size: 100 });
      setMessages(data.messages ?? []);
    } catch {
      toast.error("Failed to load messages");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOutreach();
  }, [loadOutreach]);

  const handleTestLinkedIn = async () => {
    setConnectionStatus("testing");
    setChallengeMessage("");
    toast("Logging in to LinkedIn via Selenium browser… this may take up to 2 minutes if a challenge appears.", { icon: "\u23f3", duration: 6000 });
    try {
      const { data } = await recruitersApi.testLinkedIn();
      if (data.connected) {
        setConnectionStatus("connected");
        toast.success(data.message || "Connected!");
      } else if (data.challenge) {
        setConnectionStatus("challenge");
        setChallengeMessage(data.message || "");
        toast.error("Security challenge — solve it in the VNC viewer", { duration: 8000 });
      } else {
        setConnectionStatus("failed");
        toast.error(data.message || "Connection failed");
      }
    } catch (err: unknown) {
      setConnectionStatus("failed");
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to test connection";
      toast.error(msg);
    }
  };

  const handleFetchInbox = async () => {
    setInboxLoading(true);
    setInboxMessage("");
    try {
      const { data } = await recruitersApi.fetchLinkedInInbox(5);
      if (data.success || data.connected) {
        setConversations(data.conversations ?? []);
        setInboxMessage(data.message || `Found ${(data.conversations ?? []).length} conversations`);
        setConnectionStatus("connected");
        if ((data.conversations ?? []).length === 0) {
          toast.success(data.message || "Connected but no conversations found");
        } else {
          toast.success(`Fetched ${(data.conversations ?? []).length} conversations from LinkedIn`);
        }
      } else {
        setConnectionStatus("failed");
        setInboxMessage(data.error || "Failed to fetch inbox");
        toast.error(data.error || "Failed to fetch inbox");
      }
    } catch (err: unknown) {
      setConnectionStatus("failed");
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to fetch inbox";
      setInboxMessage(msg);
      toast.error(msg);
    } finally {
      setInboxLoading(false);
    }
  };

  const filtered = filter === "all" ? messages : messages.filter((m) => m.status === filter);
  const stats = {
    total: messages.length,
    pending: messages.filter((m) => m.status === "pending").length,
    sent: messages.filter((m) => ["sent", "delivered"].includes(m.status)).length,
    failed: messages.filter((m) => m.status === "failed").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <FiLinkedin className="h-6 w-6 text-[#0A66C2]" /> LinkedIn Messages
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Real-time LinkedIn inbox &amp; outreach tracking
          </p>
        </div>
        <button onClick={loadOutreach} className="btn-secondary flex items-center gap-1 text-sm">
          <FiRefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-2 border-b border-[var(--border)] pb-0">
        <button
          onClick={() => setTab("inbox")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "inbox"
              ? "border-[#0A66C2] text-[#0A66C2]"
              : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          <FiInbox className="inline h-4 w-4 mr-1 -mt-0.5" /> LinkedIn Inbox
        </button>
        <button
          onClick={() => setTab("outreach")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "outreach"
              ? "border-[#0A66C2] text-[#0A66C2]"
              : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          <FiSend className="inline h-4 w-4 mr-1 -mt-0.5" /> Outreach Messages
          {stats.total > 0 && <span className="ml-1 badge badge-gray text-[10px]">{stats.total}</span>}
        </button>
      </div>

      {/* ==================== LINKEDIN INBOX TAB ==================== */}
      {tab === "inbox" && (
        <div className="space-y-4">
          {/* Connection test card */}
          <div className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-full ${
                  connectionStatus === "connected" ? "bg-green-100 dark:bg-green-900/30" :
                  connectionStatus === "failed" ? "bg-red-100 dark:bg-red-900/30" :
                  connectionStatus === "challenge" ? "bg-yellow-100 dark:bg-yellow-900/30" :
                  "bg-gray-100 dark:bg-gray-800"
                }`}>
                  <FiWifi className={`h-5 w-5 ${
                    connectionStatus === "connected" ? "text-green-600" :
                    connectionStatus === "failed" ? "text-red-500" :
                    connectionStatus === "challenge" ? "text-yellow-500" :
                    "text-[var(--muted-foreground)]"
                  }`} />
                </div>
                <div>
                  <h3 className="font-semibold text-[var(--foreground)]">LinkedIn Connection</h3>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {connectionStatus === "connected" && "Connected to LinkedIn successfully"}
                    {connectionStatus === "failed" && "Connection failed \u2014 check your credentials in Settings"}
                    {connectionStatus === "testing" && "Testing connection\u2026 this may take up to 2 minutes"}
                    {connectionStatus === "challenge" && "Security challenge detected \u2014 solve it in the VNC viewer"}
                    {connectionStatus === "unknown" && "Test your LinkedIn credentials before fetching messages"}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleTestLinkedIn}
                  disabled={connectionStatus === "testing"}
                  className="btn-secondary flex items-center gap-1 text-sm"
                >
                  {connectionStatus === "testing" ? (
                    <FiLoader className="h-4 w-4 animate-spin" />
                  ) : (
                    <FiWifi className="h-4 w-4" />
                  )}
                  Test Connection
                </button>
                <button
                  onClick={handleFetchInbox}
                  disabled={inboxLoading}
                  className="btn-primary flex items-center gap-1 text-sm"
                >
                  {inboxLoading ? (
                    <FiLoader className="h-4 w-4 animate-spin" />
                  ) : (
                    <FiInbox className="h-4 w-4" />
                  )}
                  Fetch Inbox (5)
                </button>
              </div>
            </div>
          </div>

          {/* VNC instructions for challenge */}
          {connectionStatus === "challenge" && (
            <div className="card border-yellow-400 dark:border-yellow-600 bg-yellow-50 dark:bg-yellow-900/20">
              <h4 className="font-semibold text-yellow-700 dark:text-yellow-400 mb-1">\u26a0\ufe0f Security Challenge Detected</h4>
              <p className="text-sm text-yellow-700 dark:text-yellow-300 mb-2">
                LinkedIn wants to verify it\u2019s really you. Follow these steps:
              </p>
              <ol className="text-sm text-yellow-700 dark:text-yellow-300 list-decimal ml-5 space-y-1">
                <li>
                  Open <a href="http://localhost:7900" target="_blank" rel="noopener noreferrer" className="underline font-medium">http://localhost:7900</a> in a new browser tab (password: <code className="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">secret</code>)
                </li>
                <li>You\u2019ll see the Selenium Chrome browser with LinkedIn\u2019s verification page</li>
                <li>Solve the CAPTCHA / email verification / phone check</li>
                <li>Once solved, click \u201cTest Connection\u201d again \u2014 cookies will be saved for future logins</li>
              </ol>
              {challengeMessage && <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-2 italic">{challengeMessage}</p>}
            </div>
          )}

          {inboxMessage && connectionStatus !== "challenge" && (
            <p className="text-sm text-[var(--muted-foreground)] italic">{inboxMessage}</p>
          )}

          {/* Inbox loading spinner */}
          {inboxLoading && (
            <div className="flex flex-col items-center py-12 gap-2">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#0A66C2] border-t-transparent" />
              <p className="text-sm text-[var(--muted-foreground)]">Logging in to LinkedIn and fetching messages…</p>
            </div>
          )}

          {/* Conversation cards */}
          {!inboxLoading && conversations.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Recent Conversations</h3>
              {conversations.map((c, i) => (
                <div key={i} className="card hover:shadow-md transition-shadow flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1 h-10 w-10 rounded-full bg-[#0A66C2] flex items-center justify-center text-white font-bold text-sm">
                    {(c.sender_name ?? "?")[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-[var(--foreground)] truncate">
                        {c.sender_name || "Unknown"}
                      </h4>
                      {c.unread && <span className="badge badge-blue text-[10px]">Unread</span>}
                    </div>
                    <p className="text-sm text-[var(--muted-foreground)] line-clamp-2">
                      {c.last_message || "No message preview"}
                    </p>
                    {c.timestamp && (
                      <p className="text-xs text-[var(--muted-foreground)] mt-1">{c.timestamp}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {!inboxLoading && conversations.length === 0 && connectionStatus !== "testing" && (
            <div className="card text-center py-12">
              <FiInbox className="mx-auto h-8 w-8 text-[var(--muted-foreground)] mb-2" />
              <p className="text-[var(--muted-foreground)]">
                Click &ldquo;Fetch Inbox&rdquo; to load your recent LinkedIn conversations.
              </p>
              <p className="text-xs text-[var(--muted-foreground)] mt-1">
                Make sure your LinkedIn credentials are saved in Settings first.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ==================== OUTREACH MESSAGES TAB ==================== */}
      {tab === "outreach" && (
        <div className="space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="card text-center">
              <p className="text-2xl font-bold text-[var(--foreground)]">{stats.total}</p>
              <p className="text-xs text-[var(--muted-foreground)]">Total</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-yellow-500">{stats.pending}</p>
              <p className="text-xs text-[var(--muted-foreground)]">Pending</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-green-500">{stats.sent}</p>
              <p className="text-xs text-[var(--muted-foreground)]">Sent</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-red-500">{stats.failed}</p>
              <p className="text-xs text-[var(--muted-foreground)]">Failed</p>
            </div>
          </div>

          {/* Filter */}
          <div className="flex flex-wrap gap-2">
            {["all", "pending", "sent", "delivered", "failed"].map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`badge cursor-pointer ${
                  filter === s ? (s === "all" ? "badge-blue" : statusConfig[s]?.badge || "badge-gray") : "badge-gray"
                }`}
              >
                {capitalize(s)}
              </button>
            ))}
          </div>

          {/* Message list */}
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="card text-center py-12">
              <FiMessageSquare className="mx-auto h-8 w-8 text-[var(--muted-foreground)] mb-2" />
              <p className="text-[var(--muted-foreground)]">
                {filter === "all" ? "No outreach messages yet." : `No ${filter} messages.`}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((msg) => {
                const expanded = expandedId === msg.id;
                const cfg = statusConfig[msg.status] || statusConfig.pending;
                return (
                  <div key={msg.id} className="card hover:shadow-md transition-shadow">
                    <button onClick={() => setExpandedId(expanded ? null : msg.id)} className="w-full text-left">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {cfg.icon}
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold text-[var(--foreground)]">{msg.recruiter_name}</h3>
                              <span className={`badge ${cfg.badge} text-[10px]`}>{capitalize(msg.status)}</span>
                              {msg.ai_generated && <span className="badge badge-blue text-[10px]">AI</span>}
                            </div>
                            <p className="text-sm text-[var(--muted-foreground)]">
                              {msg.recruiter_title} at {msg.recruiter_company}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <span className="badge badge-gray text-[10px]">
                              {typeLabels[msg.message_type] || capitalize(msg.message_type)}
                            </span>
                            <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                              {msg.sent_at ? `Sent ${formatDate(msg.sent_at)}` : msg.created_at ? `Created ${formatDate(msg.created_at)}` : ""}
                            </p>
                          </div>
                          {expanded ? <FiChevronUp className="h-4 w-4 text-[var(--muted-foreground)]" /> : <FiChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />}
                        </div>
                      </div>
                    </button>

                    {expanded && (
                      <div className="mt-3 pt-3 border-t border-[var(--border)]">
                        {msg.subject && <p className="text-sm font-medium text-[var(--foreground)] mb-1">Subject: {msg.subject}</p>}
                        <div className="bg-[var(--muted)] rounded-lg p-3 text-sm whitespace-pre-wrap">{msg.body}</div>
                        {msg.error_message && (
                          <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 rounded text-xs text-red-600 dark:text-red-400">
                            Error: {msg.error_message}
                          </div>
                        )}
                        {msg.status === "pending" && (
                          <div className="mt-2 flex justify-end">
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                try {
                                  await recruitersApi.sendOutreach(msg.recruiter_id, {
                                    message_type: msg.message_type,
                                    custom_message: msg.body,
                                  });
                                  toast.success("Message queued for sending");
                                  loadOutreach();
                                } catch {
                                  toast.error("Failed to send");
                                }
                              }}
                              className="btn-primary flex items-center gap-1 text-xs"
                            >
                              <FiSend className="h-3.5 w-3.5" /> Send Now
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
