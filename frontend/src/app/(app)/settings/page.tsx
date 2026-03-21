"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/stores/authStore";
import toast from "react-hot-toast";
import { authApi, onboardingApi, targetCompaniesApi } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";

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
  const { theme, setTheme } = useTheme();

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
  const [targetRoles, setTargetRoles] = useState("");
  const [preferredTech, setPreferredTech] = useState("");
  const [preferredCompanies, setPreferredCompanies] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [emailForOutreach, setEmailForOutreach] = useState("");
  const [remotePref, setRemotePref] = useState("");
  const [jobTypePref, setJobTypePref] = useState("");
  const [relocate, setRelocate] = useState(false);
  const [prefSaving, setPrefSaving] = useState(false);

  // Personal Info
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [nationality, setNationality] = useState("");
  const [personalSaving, setPersonalSaving] = useState(false);

  // Work
  const [currentCompany, setCurrentCompany] = useState("");
  const [currentTitle, setCurrentTitle] = useState("");
  const [yearsExp, setYearsExp] = useState("");
  const [noticePeriod, setNoticePeriod] = useState("");
  const [workAuth, setWorkAuth] = useState("");
  const [workSaving, setWorkSaving] = useState(false);

  // Salary
  const [salaryBase, setSalaryBase] = useState("");
  const [salaryBonus, setSalaryBonus] = useState("");
  const [salaryRsu, setSalaryRsu] = useState("");
  const [salaryCurrency, setSalaryCurrency] = useState("USD");
  const [expectedMin, setExpectedMin] = useState("");
  const [expectedMax, setExpectedMax] = useState("");
  const [salarySaving, setSalarySaving] = useState(false);

  // Skills
  const [skillInput, setSkillInput] = useState("");
  const [rawSkills, setRawSkills] = useState<string[]>([]);
  const [classifiedSkills, setClassifiedSkills] = useState<Record<string, string[]> | null>(null);
  const [classifying, setClassifying] = useState(false);
  const [skillsSaving, setSkillsSaving] = useState(false);

  // Delete
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Job Search Mode
  const [companySearchEnabled, setCompanySearchEnabled] = useState(false);
  const [linkedinSearchEnabled, setLinkedinSearchEnabled] = useState(true);
  const [autoApplyThreshold, setAutoApplyThreshold] = useState("");
  const [searchModeSaving, setSearchModeSaving] = useState(false);

  // Initialize from user profile
  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setKeywords(user.job_search_keywords || "");
      setPrefLocation(user.preferred_location || "");
      setTargetRoles(user.target_roles || "");
      setPreferredTech(user.preferred_technologies || "");
      setPreferredCompanies(user.preferred_companies || "");
      setExperienceLevel(user.experience_level || "");
      setEmailForOutreach(user.email_for_outreach || "");
      setRemotePref(user.remote_preference || "");
      setJobTypePref(user.job_type_preference || "");
      setRelocate(user.willing_to_relocate || false);
      setCurrentCompany(user.current_company || "");
      setCurrentTitle(user.current_title || "");
      setYearsExp(user.years_of_experience != null ? String(user.years_of_experience) : "");
      setSalaryCurrency(user.salary_currency || "USD");
      if (user.current_salary_ctc != null) {
        // We don't have per-component breakdown in the user store — leave blank
      }
      setExpectedMin(user.expected_salary_min != null ? String(user.expected_salary_min) : "");
      setExpectedMax(user.expected_salary_max != null ? String(user.expected_salary_max) : "");
      if (user.classified_skills) {
        setClassifiedSkills(user.classified_skills);
        const all = Object.values(user.classified_skills).flat();
        setRawSkills(all);
      }
      // Job search mode
      setCompanySearchEnabled(user.company_search_enabled ?? false);
      setLinkedinSearchEnabled(user.linkedin_search_enabled ?? true);
      setAutoApplyThreshold(user.auto_apply_threshold != null ? String(user.auto_apply_threshold) : "");
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
        target_roles: targetRoles ? targetRoles.split(",").map(s => s.trim()).filter(Boolean) : [],
        preferred_technologies: preferredTech ? preferredTech.split(",").map(s => s.trim()).filter(Boolean) : [],
        preferred_companies: preferredCompanies ? preferredCompanies.split(",").map(s => s.trim()).filter(Boolean) : [],
        experience_level: experienceLevel,
        email_for_outreach: emailForOutreach,
        willing_to_relocate: relocate,
        remote_preference: remotePref,
        job_type_preference: jobTypePref,
      });
      await refreshUser();
      toast.success("Preferences saved");
    } catch {
      toast.error("Failed to save preferences");
    } finally {
      setPrefSaving(false);
    }
  };

  // ── Personal Info ─────────────────────────────────────────────

  const handleSavePersonal = async () => {
    setPersonalSaving(true);
    try {
      await authApi.updateProfile({
        full_name: fullName,
        phone: phone || undefined,
        date_of_birth: dob || undefined,
        gender: gender || undefined,
        nationality: nationality || undefined,
      });
      await refreshUser();
      toast.success("Personal info saved");
    } catch {
      toast.error("Failed to save personal info");
    } finally {
      setPersonalSaving(false);
    }
  };

  // ── Work History ──────────────────────────────────────────────

  const handleSaveWork = async () => {
    setWorkSaving(true);
    try {
      await authApi.updateProfile({
        current_company: currentCompany || undefined,
        current_title: currentTitle || undefined,
        years_of_experience: yearsExp ? parseInt(yearsExp) : undefined,
        notice_period_days: noticePeriod ? parseInt(noticePeriod) : undefined,
        work_authorization: workAuth || undefined,
      });
      await refreshUser();
      toast.success("Work history saved");
    } catch {
      toast.error("Failed to save work history");
    } finally {
      setWorkSaving(false);
    }
  };

  // ── Salary ────────────────────────────────────────────────────

  const handleSaveSalary = async () => {
    setSalarySaving(true);
    try {
      await authApi.updateProfile({
        salary_currency: salaryCurrency,
        current_salary_base: salaryBase ? parseFloat(salaryBase) : undefined,
        current_salary_bonus: salaryBonus ? parseFloat(salaryBonus) : undefined,
        current_salary_rsu: salaryRsu ? parseFloat(salaryRsu) : undefined,
        expected_salary_min: expectedMin ? parseFloat(expectedMin) : undefined,
        expected_salary_max: expectedMax ? parseFloat(expectedMax) : undefined,
      });
      await refreshUser();
      toast.success("Salary info saved");
    } catch {
      toast.error("Failed to save salary info");
    } finally {
      setSalarySaving(false);
    }
  };

  // ── Skills ────────────────────────────────────────────────────

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !rawSkills.includes(s)) {
      setRawSkills((prev) => [...prev, s]);
      setSkillInput("");
    }
  };

  const removeSkill = (skill: string) => {
    setRawSkills((prev) => prev.filter((s) => s !== skill));
    if (classifiedSkills) {
      const updated = { ...classifiedSkills };
      for (const cat of Object.keys(updated)) {
        updated[cat] = updated[cat].filter((s) => s !== skill);
      }
      setClassifiedSkills(updated);
    }
  };

  const handleClassifySkills = async () => {
    if (rawSkills.length === 0) return;
    setClassifying(true);
    try {
      const { data } = await onboardingApi.classifySkills(rawSkills);
      setClassifiedSkills(data.classified);
      toast.success("Skills classified");
    } catch {
      toast.error("Failed to classify skills");
    } finally {
      setClassifying(false);
    }
  };

  const handleSaveSkills = async () => {
    setSkillsSaving(true);
    try {
      await authApi.updateProfile({ classified_skills: classifiedSkills || {} });
      await refreshUser();
      toast.success("Skills saved");
    } catch {
      toast.error("Failed to save skills");
    } finally {
      setSkillsSaving(false);
    }
  };

  // ── Job Search Mode ───────────────────────────────────────────

  const handleSaveSearchMode = async () => {
    setSearchModeSaving(true);
    try {
      await targetCompaniesApi.updateSettings({
        company_search_enabled: companySearchEnabled,
        linkedin_search_enabled: linkedinSearchEnabled,
        auto_apply_threshold: autoApplyThreshold ? parseFloat(autoApplyThreshold) : null,
      });
      await refreshUser();
      toast.success("Search mode updated");
    } catch {
      toast.error("Failed to update search mode");
    } finally {
      setSearchModeSaving(false);
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

      {/* ── Appearance ───────────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Appearance</h2>
        <p className="text-sm text-[var(--muted-foreground)]">Choose your preferred color theme.</p>
        <div className="flex gap-3">
          {(["light", "dark", "system"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              className={`rounded-lg border px-4 py-2 text-sm font-medium capitalize transition ${
                theme === t
                  ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-950/30 dark:text-brand-400"
                  : "border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] hover:bg-[var(--muted)]"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Personal Info ────────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Personal Information</h2>
        <p className="text-sm text-[var(--muted-foreground)]">Used for auto-filling job application forms.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Phone</label>
            <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} className="input" placeholder="+1 555-1234" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Date of Birth</label>
            <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} className="input" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Gender</label>
            <select value={gender} onChange={(e) => setGender(e.target.value)} className="input">
              <option value="">Prefer not to say</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="non_binary">Non-binary</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Nationality</label>
            <input type="text" value={nationality} onChange={(e) => setNationality(e.target.value)} className="input" placeholder="e.g. Indian, American" />
          </div>
        </div>
        <button onClick={handleSavePersonal} disabled={personalSaving} className="btn-primary">
          {personalSaving ? "Saving..." : "Save Personal Info"}
        </button>
      </div>

      {/* ── Work History ─────────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Work History</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Current Company</label>
            <input type="text" value={currentCompany} onChange={(e) => setCurrentCompany(e.target.value)} className="input" placeholder="Acme Corp" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Current Title</label>
            <input type="text" value={currentTitle} onChange={(e) => setCurrentTitle(e.target.value)} className="input" placeholder="Senior Engineer" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Years of Experience</label>
            <input type="number" min="0" max="50" value={yearsExp} onChange={(e) => setYearsExp(e.target.value)} className="input" placeholder="5" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Notice Period (days)</label>
            <input type="number" min="0" max="365" value={noticePeriod} onChange={(e) => setNoticePeriod(e.target.value)} className="input" placeholder="30" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Work Authorization</label>
            <select value={workAuth} onChange={(e) => setWorkAuth(e.target.value)} className="input">
              <option value="">Select...</option>
              <option value="citizen">Citizen</option>
              <option value="permanent_resident">Permanent Resident</option>
              <option value="h1b">H-1B Visa</option>
              <option value="l1">L-1 Visa</option>
              <option value="opt">OPT</option>
              <option value="ead">EAD</option>
              <option value="need_sponsorship">Need Sponsorship</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>
        <button onClick={handleSaveWork} disabled={workSaving} className="btn-primary">
          {workSaving ? "Saving..." : "Save Work History"}
        </button>
      </div>

      {/* ── Salary & Compensation ────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Salary & Compensation</h2>
        <p className="text-xs text-brand-600">Your salary data is private and never shared externally.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Currency</label>
            <select value={salaryCurrency} onChange={(e) => setSalaryCurrency(e.target.value)} className="input">
              <option value="USD">USD ($)</option>
              <option value="INR">INR (₹)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
              <option value="CAD">CAD (C$)</option>
              <option value="AUD">AUD (A$)</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Base Salary (annual)</label>
            <input type="number" min="0" value={salaryBase} onChange={(e) => setSalaryBase(e.target.value)} className="input" placeholder="120000" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Annual Bonus</label>
            <input type="number" min="0" value={salaryBonus} onChange={(e) => setSalaryBonus(e.target.value)} className="input" placeholder="15000" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Annual RSU / Equity</label>
            <input type="number" min="0" value={salaryRsu} onChange={(e) => setSalaryRsu(e.target.value)} className="input" placeholder="25000" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Expected Min ({salaryCurrency})</label>
            <input type="number" min="0" value={expectedMin} onChange={(e) => setExpectedMin(e.target.value)} className="input" placeholder="150000" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">Expected Max ({salaryCurrency})</label>
            <input type="number" min="0" value={expectedMax} onChange={(e) => setExpectedMax(e.target.value)} className="input" placeholder="200000" />
          </div>
        </div>
        <button onClick={handleSaveSalary} disabled={salarySaving} className="btn-primary">
          {salarySaving ? "Saving..." : "Save Salary Info"}
        </button>
      </div>

      {/* ── Skills ───────────────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Skills</h2>
        <p className="text-sm text-[var(--muted-foreground)]">Add skills and classify them with AI.</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={skillInput}
            onChange={(e) => setSkillInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSkill(); } }}
            className="input flex-1"
            placeholder="Type a skill and press Enter"
          />
          <button onClick={addSkill} className="btn-primary">Add</button>
        </div>
        {rawSkills.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {rawSkills.map((skill) => (
              <span key={skill} className="inline-flex items-center gap-1 rounded-full bg-[var(--muted)] px-3 py-1 text-sm">
                {skill}
                <button onClick={() => removeSkill(skill)} className="ml-1 text-[var(--muted-foreground)] hover:text-red-500">×</button>
              </span>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          {rawSkills.length > 0 && (
            <button onClick={handleClassifySkills} disabled={classifying} className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50">
              {classifying ? "Classifying..." : "Classify with AI"}
            </button>
          )}
          <button onClick={handleSaveSkills} disabled={skillsSaving || rawSkills.length === 0} className="btn-primary">
            {skillsSaving ? "Saving..." : "Save Skills"}
          </button>
        </div>
        {classifiedSkills && (
          <div className="space-y-2">
            {Object.entries(classifiedSkills).map(([cat, skills]) => {
              if (!skills || skills.length === 0) return null;
              return (
                <div key={cat}>
                  <span className="text-sm font-medium text-[var(--muted-foreground)]">{cat}</span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {skills.map((s: string) => (
                      <span key={s} className="inline-block rounded-full bg-brand-100 dark:bg-brand-900 px-3 py-1 text-xs font-medium text-brand-700 dark:text-brand-300">{s}</span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
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
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Target Roles (comma-separated)
          </label>
          <input
            type="text"
            value={targetRoles}
            onChange={(e) => setTargetRoles(e.target.value)}
            placeholder="e.g., ML Engineer, Data Scientist"
            className="input"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Preferred Technologies (comma-separated)
          </label>
          <input
            type="text"
            value={preferredTech}
            onChange={(e) => setPreferredTech(e.target.value)}
            placeholder="e.g., Python, PyTorch, Kubernetes"
            className="input"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Preferred Companies (comma-separated)
          </label>
          <input
            type="text"
            value={preferredCompanies}
            onChange={(e) => setPreferredCompanies(e.target.value)}
            placeholder="e.g., Google, Meta, OpenAI"
            className="input"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Experience Level
          </label>
          <select
            value={experienceLevel}
            onChange={(e) => setExperienceLevel(e.target.value)}
            className="input"
          >
            <option value="">Select...</option>
            <option value="intern">Intern</option>
            <option value="junior">Junior (0-2 years)</option>
            <option value="mid">Mid-level (2-5 years)</option>
            <option value="senior">Senior (5-10 years)</option>
            <option value="staff">Staff / Principal (10+ years)</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Email for Outreach
          </label>
          <input
            type="email"
            value={emailForOutreach}
            onChange={(e) => setEmailForOutreach(e.target.value)}
            placeholder="recruiter-facing email address"
            className="input"
          />
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            Used in recruiter outreach messages. Defaults to your login email if blank.
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Remote Preference
          </label>
          <select value={remotePref} onChange={(e) => setRemotePref(e.target.value)} className="input">
            <option value="">Any</option>
            <option value="remote">Remote Only</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
            Job Type
          </label>
          <select value={jobTypePref} onChange={(e) => setJobTypePref(e.target.value)} className="input">
            <option value="">Any</option>
            <option value="full_time">Full Time</option>
            <option value="contract">Contract</option>
            <option value="either">Either</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input type="checkbox" id="relocate-pref" checked={relocate} onChange={(e) => setRelocate(e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
          <label htmlFor="relocate-pref" className="text-sm text-[var(--foreground)]">Willing to relocate</label>
        </div>
        <button
          onClick={handleSavePreferences}
          disabled={prefSaving}
          className="btn-primary"
        >
          {prefSaving ? "Saving..." : "Save Preferences"}
        </button>
      </div>

      {/* ── Job Search Mode ──────────────────────────────────── */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Job Search Mode</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Choose how jobs are discovered. You can use LinkedIn, company career pages, or both.
        </p>
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3">
            <div>
              <p className="font-medium text-[var(--foreground)]">LinkedIn Search</p>
              <p className="text-xs text-[var(--muted-foreground)]">Search for jobs via LinkedIn, Indeed, and other job boards</p>
            </div>
            <button
              onClick={() => setLinkedinSearchEnabled(!linkedinSearchEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                linkedinSearchEnabled ? "bg-brand-600" : "bg-gray-300 dark:bg-gray-600"
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                linkedinSearchEnabled ? "translate-x-6" : "translate-x-1"
              }`} />
            </button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3">
            <div>
              <p className="font-medium text-[var(--foreground)]">Company Career Page Search</p>
              <p className="text-xs text-[var(--muted-foreground)]">Automatically scrape career pages of your target companies</p>
            </div>
            <button
              onClick={() => setCompanySearchEnabled(!companySearchEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                companySearchEnabled ? "bg-brand-600" : "bg-gray-300 dark:bg-gray-600"
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                companySearchEnabled ? "translate-x-6" : "translate-x-1"
              }`} />
            </button>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
              Auto-Apply Threshold (match score %)
            </label>
            <input
              type="number"
              min="0"
              max="100"
              step="5"
              value={autoApplyThreshold}
              onChange={(e) => setAutoApplyThreshold(e.target.value)}
              className="input w-40"
              placeholder="e.g. 80"
            />
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              Automatically apply when job match score exceeds this percentage. Leave blank to disable auto-apply.
            </p>
          </div>
        </div>
        <button
          onClick={handleSaveSearchMode}
          disabled={searchModeSaving}
          className="btn-primary"
        >
          {searchModeSaving ? "Saving..." : "Save Search Mode"}
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
