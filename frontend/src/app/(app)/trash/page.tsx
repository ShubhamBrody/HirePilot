"use client";

import { useEffect, useState, useCallback } from "react";
import { FiTrash2, FiRotateCcw, FiAlertTriangle } from "react-icons/fi";
import { trashApi } from "@/lib/api";
import toast from "react-hot-toast";

interface TrashItem {
  id: string;
  type: string;
  deleted_at: string;
  company?: string;
  role?: string;
  title?: string;
  name?: string;
  status?: string;
  is_master?: boolean;
}

interface TrashData {
  [key: string]: {
    items: TrashItem[];
    count: number;
  };
}

const TYPE_LABELS: Record<string, string> = {
  application: "Applications",
  job: "Jobs",
  resume: "Resumes",
  recruiter: "Recruiters",
};

export default function TrashPage() {
  const [trashData, setTrashData] = useState<TrashData>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [showEmptyConfirm, setShowEmptyConfirm] = useState(false);

  const loadTrash = useCallback(async () => {
    try {
      setLoading(true);
      const params = activeTab !== "all" ? { item_type: activeTab } : {};
      const { data } = await trashApi.list(params);
      setTrashData(data);
    } catch {
      toast.error("Failed to load trash");
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadTrash();
  }, [loadTrash]);

  const totalCount = Object.values(trashData).reduce(
    (sum, bucket) => sum + (bucket?.count || 0),
    0
  );

  const handleRestore = async (type: string, id: string) => {
    try {
      await trashApi.restore(type, id);
      toast.success("Item restored");
      loadTrash();
    } catch {
      toast.error("Failed to restore item");
    }
  };

  const handlePermanentDelete = async (type: string, id: string) => {
    try {
      await trashApi.permanentDelete(type, id);
      toast.success("Permanently deleted");
      loadTrash();
    } catch {
      toast.error("Failed to delete item");
    }
  };

  const handleEmptyTrash = async () => {
    try {
      await trashApi.empty();
      toast.success("Trash emptied");
      setShowEmptyConfirm(false);
      loadTrash();
    } catch {
      toast.error("Failed to empty trash");
    }
  };

  const formatDeletedAt = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    const remaining = 20 - diff;
    return remaining > 0
      ? `${remaining} day${remaining !== 1 ? "s" : ""} until permanent deletion`
      : "Scheduled for deletion";
  };

  const getItemLabel = (item: TrashItem) => {
    if (item.type === "application") return `${item.role} @ ${item.company}`;
    if (item.type === "job") return `${item.title} @ ${item.company}`;
    if (item.type === "resume") return item.name || "Untitled Resume";
    if (item.type === "recruiter") return `${item.name} — ${item.company}`;
    return item.id;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Trash</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            {totalCount} item{totalCount !== 1 ? "s" : ""} &middot; Items are automatically
            deleted after 20 days
          </p>
        </div>
        {totalCount > 0 && (
          <button
            onClick={() => setShowEmptyConfirm(true)}
            className="btn btn-sm bg-red-600 text-white hover:bg-red-700"
          >
            <FiTrash2 className="mr-1.5 h-4 w-4" />
            Empty Trash
          </button>
        )}
      </div>

      {/* Empty confirm dialog */}
      {showEmptyConfirm && (
        <div className="card border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-4">
          <div className="flex items-center gap-3">
            <FiAlertTriangle className="h-5 w-5 text-red-600 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-red-700 dark:text-red-400">
                Permanently delete all {totalCount} items?
              </p>
              <p className="text-sm text-red-600 dark:text-red-300 mt-0.5">
                This action cannot be undone.
              </p>
            </div>
            <button
              onClick={handleEmptyTrash}
              className="btn btn-sm bg-red-600 text-white hover:bg-red-700"
            >
              Delete All
            </button>
            <button
              onClick={() => setShowEmptyConfirm(false)}
              className="btn btn-sm bg-[var(--muted)] text-[var(--foreground)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Type filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveTab("all")}
          className={`badge cursor-pointer ${
            activeTab === "all" ? "badge-blue" : "badge-gray"
          }`}
        >
          All
        </button>
        {Object.entries(TYPE_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`badge cursor-pointer ${
              activeTab === key ? "badge-blue" : "badge-gray"
            }`}
          >
            {label} ({trashData[key]?.count || 0})
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        </div>
      ) : totalCount === 0 ? (
        <div className="card text-center py-12">
          <FiTrash2 className="mx-auto h-12 w-12 text-[var(--muted-foreground)] mb-3" />
          <p className="text-[var(--muted-foreground)]">Trash is empty</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(trashData).map(([type, bucket]) => {
            if (!bucket?.items?.length) return null;
            if (activeTab !== "all" && activeTab !== type) return null;
            return (
              <div key={type}>
                {activeTab === "all" && (
                  <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">
                    {TYPE_LABELS[type] || type}
                  </h2>
                )}
                <div className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
                  {bucket.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between px-4 py-3 hover:bg-[var(--muted)] transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-[var(--foreground)] truncate">
                          {getItemLabel(item)}
                        </p>
                        <p className="text-xs text-[var(--muted-foreground)]">
                          {item.deleted_at && formatDeletedAt(item.deleted_at)}
                          {item.status && (
                            <span className="ml-2 badge badge-gray text-xs">
                              {item.status}
                            </span>
                          )}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <button
                          onClick={() => handleRestore(type, item.id)}
                          className="btn btn-sm bg-[var(--muted)] text-[var(--foreground)] hover:bg-brand-50 hover:text-brand-700"
                          title="Restore"
                        >
                          <FiRotateCcw className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handlePermanentDelete(type, item.id)}
                          className="btn btn-sm bg-[var(--muted)] text-[var(--foreground)] hover:bg-red-50 hover:text-red-600"
                          title="Delete permanently"
                        >
                          <FiTrash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
