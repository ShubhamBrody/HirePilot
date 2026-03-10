"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/stores/authStore";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";

interface CredentialStatus {
  platform: string;
  configured: boolean;
  username: string | null;
}

const PLATFORM_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  naukri: "Naukri",
};

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const refreshUser = useAuthStore((s) => s.refreshUser);

  // Profile
  const [fullName, setFullName] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);

  // Password
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);

  // Credentials
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [credModalOpen, setCredModalOpen] = useState<string | null>(null);
  const [credUsername, setCredUsername] = useState("");
  const [credPassword, setCredPassword] = useState("");
  const [credSaving, setCredSaving] = useState(false);

  // Preferences
  const [keywords, setKeywords] = useState("");
  const [prefLocation, setPrefLocation] = useState("");
  const [prefSaving, setPrefSaving] = useState(false);

  // Delete
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Initialize from user profile
  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setKeywords(user.job_search_keywords || "");
      setPrefLocation(user.preferred_location || "");
    }
  }, [user]);

  // Load credential statuses
  const loadCredentials = useCallback(async () => {
    try {
      const { data } = await authApi.getCredentials();
      setCredentials(data);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadCredentials();
  }, [loadCredentials]);

  // ── Profile Save ──────────────────────────────────────────────

  const handleUpdateProfile = async () => {
    setProfileSaving(true);
    try {
      await authApi.updateProfile({ full_name: fullName });
      await refreshUser();
      toast.success("Profile updated");
    } catch {
      toast.error("Failed to update profile");
    } finally {
      setProfileSaving(false);
    }
  };

  // ── Password Change ───────────────────────────────────────────

  const handleChangePassword = async () => {
    if (newPw !== confirmPw) {
      toast.error("Passwords do not match");
      return;
    }
    if (newPw.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setPwSaving(true);
    try {
      await authApi.changePassword({
        current_password: currentPw,
        new_password: newPw,
      });
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      toast.success("Password changed");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to change password";
      toast.error(msg);
    } finally {
      setPwSaving(false);
    }
  };

  // ── Credentials ───────────────────────────────────────────────

  const openCredModal = (platform: string) => {
    const existing = credentials.find((c) => c.platform === platform);
    setCredUsername(existing?.username || "");
    setCredPassword("");
    setCredModalOpen(platform);
  };

  const handleSaveCredential = async () => {
    if (!credModalOpen) return;
    if (!credUsername.trim() || !credPassword.trim()) {
      toast.error("Username and password are required");
      return;
    }
    setCredSaving(true);
    try {
      await authApi.saveCredential({
        platform: credModalOpen,
        username: credUsername,
        password: credPassword,
      });
      toast.success(`${PLATFORM_LABELS[credModalOpen]} credentials saved`);
      setCredModalOpen(null);
      await loadCredentials();
    } catch {
      toast.error("Failed to save credentials");
    } finally {
      setCredSaving(false);
    }
  };

  const handleDeleteCredential = async (platform: string) => {
    try {
      await authApi.deleteCredential(platform);
      toast.success(`${PLATFORM_LABELS[platform]} credentials removed`);
      await loadCredentials();
    } catch {
      toast.error("Failed to remove credentials");
    }
  };

  // ── Preferences ───────────────────────────────────────────────

  const handleSavePreferences = async () => {
    setPrefSaving(true);
    try {
      await authApi.updatePreferences({
        job_search_keywords: keywords,
        preferred_location: prefLocation,
      });
      await refreshUser();
      toast.success("Preferences saved");
    } catch {
      toast.error("Failed to save preferences");
    } finally {
      setPrefSaving(false);
    }
  };

  // ── Delete Account ────────────────────────────────────────────

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await authApi.deleteAccount();
      toast.success("Account deleted");
      logout();
    } catch {
      toast.error("Failed to delete account");
    } finally {
      setDeleting(false);
      setDeleteConfirm(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Settings</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Manage your account and platform preferences
        </p>
      </div>

      {/* ── Profile ──────────────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Profile</h2>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Email
          </label>
          <input
            type="email"
            value={user?.email || ""}
            disabled
            className="input bg-[var(--muted)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Full Name
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="input"
          />
        </div>
        <button
          onClick={handleUpdateProfile}
          disabled={profileSaving}
          className="btn-primary"
        >
          {profileSaving ? "Saving..." : "Save Changes"}
        </button>
      </div>

      {/* ── Change Password ──────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Change Password
        </h2>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Current Password
          </label>
          <input
            type="password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
            className="input"
            placeholder="Enter current password"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            New Password
          </label>
          <input
            type="password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            className="input"
            placeholder="Min 8 characters"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Confirm New Password
          </label>
          <input
            type="password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            className="input"
            placeholder="Re-enter new password"
          />
        </div>
        <button
          onClick={handleChangePassword}
          disabled={pwSaving || !currentPw || !newPw || !confirmPw}
          className="btn-primary"
        >
          {pwSaving ? "Changing..." : "Change Password"}
        </button>
      </div>

      {/* ── Platform Credentials ─────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Platform Credentials
        </h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Store encrypted credentials for automated job applications and recruiter
          outreach. All credentials are AES-256 encrypted at rest.
        </p>
        <div className="space-y-3">
          {["linkedin", "indeed", "naukri"].map((platform) => {
            const cred = credentials.find((c) => c.platform === platform);
            return (
              <div
                key={platform}
                className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3"
              >
                <div>
                  <p className="font-medium text-[var(--foreground)]">
                    {PLATFORM_LABELS[platform]}
                  </p>
                  {cred?.configured ? (
                    <p className="text-xs text-green-600">
                      Configured as {cred.username}
                    </p>
                  ) : (
                    <p className="text-xs text-[var(--muted-foreground)]">
                      Not configured
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openCredModal(platform)}
                    className="btn-secondary text-xs"
                  >
                    {cred?.configured ? "Update" : "Configure"}
                  </button>
                  {cred?.configured && (
                    <button
                      onClick={() => handleDeleteCredential(platform)}
                      className="rounded-md border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Credential Modal ─────────────────────────────────── */}
      {credModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-[var(--card)] p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold text-[var(--foreground)]">
              Configure {PLATFORM_LABELS[credModalOpen]}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
                  Username / Email
                </label>
                <input
                  type="text"
                  value={credUsername}
                  onChange={(e) => setCredUsername(e.target.value)}
                  className="input"
                  placeholder="Enter your username or email"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
                  Password
                </label>
                <input
                  type="password"
                  value={credPassword}
                  onChange={(e) => setCredPassword(e.target.value)}
                  className="input"
                  placeholder="Enter your password"
                />
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">
                Your credentials are encrypted with AES-256 before storage and
                are only decrypted during automated login sessions.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setCredModalOpen(null)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveCredential}
                  disabled={credSaving}
                  className="btn-primary"
                >
                  {credSaving ? "Saving..." : "Save Credentials"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Job Search Preferences ───────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Job Search Preferences
        </h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Set your default job search keywords and locations for automated scraping.
        </p>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Keywords (comma-separated)
          </label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., Software Engineer, Full Stack Developer"
            className="input"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Preferred Location
          </label>
          <input
            type="text"
            value={prefLocation}
            onChange={(e) => setPrefLocation(e.target.value)}
            placeholder="e.g., San Francisco, Remote"
            className="input"
          />
        </div>
        <button
          onClick={handleSavePreferences}
          disabled={prefSaving}
          className="btn-primary"
        >
          {prefSaving ? "Saving..." : "Save Preferences"}
        </button>
      </div>

      {/* ── Danger Zone ──────────────────────────────────────── */}
      <div className="card border-red-200 dark:border-red-900/50 space-y-4">
        <h2 className="text-lg font-semibold text-red-600">Danger Zone</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Irreversible actions. Proceed with caution.
        </p>
        {!deleteConfirm ? (
          <button
            onClick={() => setDeleteConfirm(true)}
            className="btn-danger"
          >
            Delete Account
          </button>
        ) : (
          <div className="space-y-3 rounded-lg border border-red-300 p-4 dark:border-red-800">
            <p className="text-sm font-medium text-red-600">
              Are you sure? This will permanently delete your account and all
              associated data. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleDeleteAccount}
                disabled={deleting}
                className="btn-danger"
              >
                {deleting ? "Deleting..." : "Yes, Delete My Account"}
              </button>
              <button
                onClick={() => setDeleteConfirm(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
