"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [saving, setSaving] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");

  const handleUpdateProfile = async () => {
    setSaving(true);
    try {
      await authApi.updateProfile({ full_name: fullName });
      toast.success("Profile updated");
    } catch {
      toast.error("Failed to update profile");
    } finally {
      setSaving(false);
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

      {/* Profile */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Profile</h2>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Email
          </label>
          <input type="email" value={user?.email || ""} disabled className="input bg-[var(--muted)]" />
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
        <button onClick={handleUpdateProfile} disabled={saving} className="btn-primary">
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>

      {/* Platform Credentials */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Platform Credentials
        </h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Store encrypted credentials for automated job applications and recruiter outreach.
          All credentials are AES-256 encrypted at rest.
        </p>
        <div className="space-y-3">
          {["LinkedIn", "Indeed", "Naukri"].map((platform) => (
            <div key={platform} className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3">
              <div>
                <p className="font-medium text-[var(--foreground)]">{platform}</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Used for automated login during scraping and applications
                </p>
              </div>
              <button className="btn-secondary text-xs">Configure</button>
            </div>
          ))}
        </div>
      </div>

      {/* Job Preferences */}
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
          <input type="text" placeholder="e.g., Software Engineer, Full Stack Developer" className="input" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Preferred Location
          </label>
          <input type="text" placeholder="e.g., San Francisco, Remote" className="input" />
        </div>
        <button className="btn-primary">Save Preferences</button>
      </div>

      {/* Danger Zone */}
      <div className="card border-red-200 dark:border-red-900/50 space-y-4">
        <h2 className="text-lg font-semibold text-red-600">Danger Zone</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Irreversible actions. Proceed with caution.
        </p>
        <button className="btn-danger">Delete Account</button>
      </div>
    </div>
  );
}
