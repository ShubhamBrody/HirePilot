"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { onboardingApi, profileApi } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

/* ──────────────── types ──────────────── */

interface StepStatus {
  [key: string]: boolean;
}

const STEP_TITLES = [
  "Personal Info",
  "Work Experience",
  "Salary & Compensation",
  "Skills",
  "Job Preferences",
  "Platform Credentials",
  "Resume",
  "Education & Review",
];

const SKILL_CATEGORIES = [
  "Languages",
  "Frameworks",
  "Databases",
  "Cloud & DevOps",
  "Tools",
  "Architecture & Patterns",
  "Soft Skills",
  "Other",
];

const CATEGORY_COLORS: Record<string, string> = {
  Languages: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  Frameworks: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  Databases: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  "Cloud & DevOps": "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  Tools: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  "Architecture & Patterns": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  "Soft Skills": "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
  Other: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
};

/* ──────────────── main component ──────────────── */

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshUser } = useAuthStore();
  const [step, setStep] = useState(1);
  const [stepsStatus, setStepsStatus] = useState<StepStatus>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Step 1
  const [fullName, setFullName] = useState("");
  const [emailOutreach, setEmailOutreach] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [nationality, setNationality] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");

  // Step 2 — multiple work experiences
  const [experiences, setExperiences] = useState([
    { company: "", role: "", location: "", description: "", start_date: "", end_date: "", is_current: false },
  ]);
  const [yearsExp, setYearsExp] = useState("");
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [noticePeriod, setNoticePeriod] = useState("");
  const [workAuth, setWorkAuth] = useState("");

  // Step 3
  const [salaryBase, setSalaryBase] = useState("");
  const [salaryBonus, setSalaryBonus] = useState("");
  const [salaryRsu, setSalaryRsu] = useState("");
  const [salaryCurrency, setSalaryCurrency] = useState("USD");
  const [expectedMin, setExpectedMin] = useState("");
  const [expectedMax, setExpectedMax] = useState("");

  // Step 4
  const [skillInput, setSkillInput] = useState("");
  const [rawSkills, setRawSkills] = useState<string[]>([]);
  const [classifiedSkills, setClassifiedSkills] = useState<Record<string, string[]> | null>(null);
  const [classifying, setClassifying] = useState(false);

  // Step 5
  const [targetRoles, setTargetRoles] = useState("");
  const [prefTech, setPrefTech] = useState("");
  const [prefCompanies, setPrefCompanies] = useState("");
  const [prefLocation, setPrefLocation] = useState("");
  const [searchKeywords, setSearchKeywords] = useState("");
  const [relocate, setRelocate] = useState(false);
  const [remotePref, setRemotePref] = useState("any");
  const [jobTypePref, setJobTypePref] = useState("full_time");

  // Step 6
  const [liUsername, setLiUsername] = useState("");
  const [liPassword, setLiPassword] = useState("");
  const [indeedUsername, setIndeedUsername] = useState("");
  const [indeedPassword, setIndeedPassword] = useState("");
  const [naukriUsername, setNaukriUsername] = useState("");
  const [naukriPassword, setNaukriPassword] = useState("");

  // Step 7
  const [resumeMode, setResumeMode] = useState<"latex" | "pdf">("latex");
  const [latexSource, setLatexSource] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [convertedLatex, setConvertedLatex] = useState("");
  const [uploading, setUploading] = useState(false);

  // Step 8 — structured education with degree dropdowns
  const [education, setEducation] = useState([
    { degree: "", custom_degree: "", field_of_study: "", custom_field: "", institution: "", start_year: "", end_year: "", gpa: "", gpa_scale: "10", activities: "" },
  ]);
  const [degreeChoices, setDegreeChoices] = useState<string[]>([]);
  const [fieldChoices, setFieldChoices] = useState<string[]>([]);
  const [disability, setDisability] = useState("");
  const [veteran, setVeteran] = useState("");
  const [coverLetter, setCoverLetter] = useState("");

  /* ──── load progress ──── */

  const loadProgress = useCallback(async () => {
    try {
      const { data } = await onboardingApi.getProgress();
      if (data.completed) {
        router.replace("/dashboard");
        return;
      }
      setStepsStatus(data.steps_status || {});
      if (data.current_step > 0 && data.current_step < 8) {
        setStep(data.current_step + 1);
      }
    } catch {
      // Ignore
    }
  }, [router]);

  useEffect(() => {
    loadProgress();
    // Load education choices
    profileApi.getEducationChoices().then(({ data }) => {
      setDegreeChoices(data.degree_choices || []);
      setFieldChoices(data.field_of_study_choices || []);
    }).catch(() => {
      // Fallback choices
      setDegreeChoices(["BTech", "BE", "BSc", "BA", "BCom", "BCA", "BBA", "MTech", "ME", "MSc", "MA", "MCom", "MCA", "MBA", "PhD", "MD", "JD", "BS", "MS", "AA", "AS", "Diploma", "Other"]);
      setFieldChoices(["Computer Science", "Information Technology", "Software Engineering", "Electrical Engineering", "Mechanical Engineering", "Data Science", "Business Administration", "Other"]);
    });
  }, [loadProgress]);

  /* ──── save handlers ──── */

  const saveCurrentStep = async () => {
    setSaving(true);
    setError("");
    try {
      switch (step) {
        case 1:
          await onboardingApi.saveStep(1, {
            full_name: fullName,
            email_for_outreach: emailOutreach || undefined,
            phone: phone || undefined,
            date_of_birth: dob || undefined,
            gender: gender || undefined,
            nationality: nationality || undefined,
            address: city || country ? { city, country } : undefined,
            linkedin_url: linkedinUrl || undefined,
            github_url: githubUrl || undefined,
            portfolio_url: portfolioUrl || undefined,
          });
          break;
        case 2: {
          const validExps = experiences.filter((e) => e.company && e.role);
          await onboardingApi.saveStep(2, {
            experiences: validExps,
            years_of_experience: yearsExp ? parseInt(yearsExp) : undefined,
            headline: headline || undefined,
            summary: summary || undefined,
            experience_level: experienceLevel || undefined,
            notice_period_days: noticePeriod ? parseInt(noticePeriod) : undefined,
            work_authorization: workAuth || undefined,
          });
          break;
        }
        case 3:
          await onboardingApi.saveStep(3, {
            current_salary_base: salaryBase ? parseFloat(salaryBase) : undefined,
            current_salary_bonus: salaryBonus ? parseFloat(salaryBonus) : undefined,
            current_salary_rsu: salaryRsu ? parseFloat(salaryRsu) : undefined,
            salary_currency: salaryCurrency,
            expected_salary_min: expectedMin ? parseFloat(expectedMin) : undefined,
            expected_salary_max: expectedMax ? parseFloat(expectedMax) : undefined,
          });
          break;
        case 4:
          await onboardingApi.saveStep(4, {
            raw_skills: rawSkills,
            classified_skills: classifiedSkills || undefined,
          });
          break;
        case 5:
          await onboardingApi.saveStep(5, {
            target_roles: targetRoles ? targetRoles.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
            preferred_technologies: prefTech ? prefTech.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
            preferred_companies: prefCompanies ? prefCompanies.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
            preferred_location: prefLocation || undefined,
            job_search_keywords: searchKeywords || undefined,
            willing_to_relocate: relocate,
            remote_preference: remotePref,
            job_type_preference: jobTypePref,
          });
          break;
        case 6: {
          const credentials = [];
          if (liUsername && liPassword) {
            credentials.push({ platform: "linkedin", username: liUsername, password: liPassword });
          }
          if (indeedUsername && indeedPassword) {
            credentials.push({ platform: "indeed", username: indeedUsername, password: indeedPassword });
          }
          if (naukriUsername && naukriPassword) {
            credentials.push({ platform: "naukri", username: naukriUsername, password: naukriPassword });
          }
          await onboardingApi.saveStep(6, { credentials });
          break;
        }
        case 7: {
          const finalLatex = resumeMode === "pdf" ? convertedLatex : latexSource;
          if (!finalLatex) {
            setError("Please provide your resume (LaTeX or PDF).");
            setSaving(false);
            return;
          }
          await onboardingApi.saveStep(7, { latex_source: finalLatex });
          break;
        }
        case 8: {
          const edu = education.filter((e) => e.degree && e.institution);
          await onboardingApi.saveStep(8, {
            education: edu.map((e) => ({
              degree: e.degree,
              custom_degree: e.degree === "Other" ? e.custom_degree : undefined,
              field_of_study: e.field_of_study || undefined,
              custom_field: e.field_of_study === "Other" ? e.custom_field : undefined,
              institution: e.institution,
              start_year: e.start_year ? parseInt(e.start_year) : undefined,
              end_year: e.end_year ? parseInt(e.end_year) : undefined,
              gpa: e.gpa || undefined,
              gpa_scale: e.gpa_scale ? parseFloat(e.gpa_scale) : undefined,
              activities: e.activities || undefined,
            })),
            disability_status: disability || undefined,
            veteran_status: veteran || undefined,
            cover_letter_default: coverLetter || undefined,
          });
          await refreshUser();
          router.replace("/dashboard");
          return;
        }
      }
      setStepsStatus((prev) => ({ ...prev, [String(step)]: true }));
      setStep((s) => s + 1);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to save";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  /* ──── skill classification ──── */

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

  const classifySkillsHandler = async () => {
    if (rawSkills.length === 0) return;
    setClassifying(true);
    try {
      const { data } = await onboardingApi.classifySkills(rawSkills);
      setClassifiedSkills(data.classified);
    } catch {
      setError("Skill classification failed. You can save and classify later.");
    } finally {
      setClassifying(false);
    }
  };

  /* ──── PDF upload ──── */

  const handlePdfUpload = async () => {
    if (!pdfFile) return;
    setUploading(true);
    setError("");
    try {
      const { data } = await onboardingApi.uploadResume(pdfFile);
      setConvertedLatex(data.latex_source);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "PDF upload failed";
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  /* ──────────────── progress bar ──────────────── */

  const progressBar = (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-[var(--foreground)]">
          Step {step} of {STEP_TITLES.length}
        </span>
        <span className="text-sm text-[var(--muted-foreground)]">
          {STEP_TITLES[step - 1]}
        </span>
      </div>
      <div className="flex gap-1.5">
        {STEP_TITLES.map((_, i) => (
          <div
            key={i}
            className={`h-2 flex-1 rounded-full transition-colors ${
              i + 1 <= step
                ? "bg-brand-600"
                : stepsStatus[String(i + 1)]
                ? "bg-brand-300"
                : "bg-[var(--muted)]"
            }`}
          />
        ))}
      </div>
    </div>
  );

  /* ──────────────── step renders ──────────────── */

  const inputClass =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";
  const labelClass = "block text-sm font-medium text-[var(--foreground)] mb-1";
  const selectClass = inputClass;

  const renderStep1 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-[var(--foreground)]">Personal Information</h2>
      <p className="text-sm text-[var(--muted-foreground)]">This info will be used to auto-fill job application forms on your behalf.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Full Name *</label>
          <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required />
        </div>
        <div>
          <label className={labelClass}>Email for Outreach</label>
          <input className={inputClass} type="email" value={emailOutreach} onChange={(e) => setEmailOutreach(e.target.value)} placeholder="recruiter-replies@example.com" />
        </div>
        <div>
          <label className={labelClass}>Phone</label>
          <input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 555-1234" />
        </div>
        <div>
          <label className={labelClass}>Date of Birth</label>
          <input className={inputClass} type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Gender</label>
          <select className={selectClass} value={gender} onChange={(e) => setGender(e.target.value)}>
            <option value="">Prefer not to say</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="non_binary">Non-binary</option>
            <option value="prefer_not_to_say">Prefer not to say</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>Nationality</label>
          <input className={inputClass} value={nationality} onChange={(e) => setNationality(e.target.value)} placeholder="e.g. Indian, American" />
        </div>
        <div>
          <label className={labelClass}>City</label>
          <input className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} placeholder="San Francisco" />
        </div>
        <div>
          <label className={labelClass}>Country</label>
          <input className={inputClass} value={country} onChange={(e) => setCountry(e.target.value)} placeholder="United States" />
        </div>
      </div>
      <h3 className="text-lg font-medium text-[var(--foreground)] pt-2">Social Links</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>LinkedIn URL</label>
          <input className={inputClass} value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} placeholder="https://linkedin.com/in/..." />
        </div>
        <div>
          <label className={labelClass}>GitHub URL</label>
          <input className={inputClass} value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} placeholder="https://github.com/..." />
        </div>
        <div>
          <label className={labelClass}>Portfolio URL</label>
          <input className={inputClass} value={portfolioUrl} onChange={(e) => setPortfolioUrl(e.target.value)} placeholder="https://yoursite.com" />
        </div>
      </div>
    </div>
  );

  const renderStep2 = () => {
    const updateExp = (i: number, field: string, value: string | boolean) => {
      const updated = [...experiences];
      (updated[i] as Record<string, string | boolean>)[field] = value;
      if (field === "is_current" && value === true) {
        updated[i].end_date = "";
      }
      setExperiences(updated);
    };
    const addExp = () => setExperiences([...experiences, { company: "", role: "", location: "", description: "", start_date: "", end_date: "", is_current: false }]);
    const removeExp = (i: number) => setExperiences(experiences.filter((_, j) => j !== i));

    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-[var(--foreground)]">Work Experience</h2>
        <p className="text-sm text-[var(--muted-foreground)]">Add all your relevant work experiences. Mark your current role with the checkbox.</p>

        {experiences.map((exp, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--foreground)]">Experience {i + 1}</span>
              {experiences.length > 1 && (
                <button onClick={() => removeExp(i)} className="text-red-500 hover:text-red-700 text-sm font-medium">Remove</button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Company *</label>
                <input className={inputClass} value={exp.company} onChange={(e) => updateExp(i, "company", e.target.value)} placeholder="Acme Corp" />
              </div>
              <div>
                <label className={labelClass}>Role / Title *</label>
                <input className={inputClass} value={exp.role} onChange={(e) => updateExp(i, "role", e.target.value)} placeholder="Senior Software Engineer" />
              </div>
              <div>
                <label className={labelClass}>Location</label>
                <input className={inputClass} value={exp.location} onChange={(e) => updateExp(i, "location", e.target.value)} placeholder="San Francisco, CA" />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input type="checkbox" id={`current-${i}`} checked={exp.is_current} onChange={(e) => updateExp(i, "is_current", e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
                <label htmlFor={`current-${i}`} className="text-sm text-[var(--foreground)]">I currently work here</label>
              </div>
              <div>
                <label className={labelClass}>Start Date</label>
                <input className={inputClass} type="date" value={exp.start_date} onChange={(e) => updateExp(i, "start_date", e.target.value)} />
              </div>
              {!exp.is_current && (
                <div>
                  <label className={labelClass}>End Date</label>
                  <input className={inputClass} type="date" value={exp.end_date} onChange={(e) => updateExp(i, "end_date", e.target.value)} />
                </div>
              )}
            </div>
            <div>
              <label className={labelClass}>Description</label>
              <textarea className={inputClass + " h-16 resize-y"} value={exp.description} onChange={(e) => updateExp(i, "description", e.target.value)} placeholder="Key responsibilities and achievements..." />
            </div>
          </div>
        ))}

        <button onClick={addExp} className="text-sm text-brand-600 hover:text-brand-700 font-medium">+ Add Another Experience</button>

        <hr className="border-[var(--border)]" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Total Years of Experience</label>
            <input className={inputClass} type="number" min="0" max="50" value={yearsExp} onChange={(e) => setYearsExp(e.target.value)} placeholder="5" />
          </div>
          <div>
            <label className={labelClass}>Experience Level</label>
            <select className={selectClass} value={experienceLevel} onChange={(e) => setExperienceLevel(e.target.value)}>
              <option value="">Select...</option>
              <option value="intern">Intern</option>
              <option value="junior">Junior (0-2 yrs)</option>
              <option value="mid">Mid (2-5 yrs)</option>
              <option value="senior">Senior (5-8 yrs)</option>
              <option value="staff">Staff (8-12 yrs)</option>
              <option value="lead">Lead / Principal (12+)</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Notice Period (days)</label>
            <input className={inputClass} type="number" min="0" max="365" value={noticePeriod} onChange={(e) => setNoticePeriod(e.target.value)} placeholder="30" />
          </div>
          <div>
            <label className={labelClass}>Work Authorization</label>
            <select className={selectClass} value={workAuth} onChange={(e) => setWorkAuth(e.target.value)}>
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
        <div>
          <label className={labelClass}>Professional Headline</label>
          <input className={inputClass} value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="Senior Backend Engineer | Python & Go | Distributed Systems" />
        </div>
        <div>
          <label className={labelClass}>Summary</label>
          <textarea className={inputClass + " h-24 resize-y"} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Brief professional summary..." />
        </div>
      </div>
    );
  };

  const renderStep3 = () => {
    const base = parseFloat(salaryBase) || 0;
    const bonus = parseFloat(salaryBonus) || 0;
    const rsu = parseFloat(salaryRsu) || 0;
    const ctc = base + bonus + rsu;
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-[var(--foreground)]">Salary & Compensation</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          This helps us find jobs that pay considerably more than what you earn now. Also useful during negotiations.
          <span className="block mt-1 text-xs text-brand-600">🔒 Your salary data is private and never shared externally.</span>
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Currency</label>
            <select className={selectClass} value={salaryCurrency} onChange={(e) => setSalaryCurrency(e.target.value)}>
              <option value="USD">USD ($)</option>
              <option value="INR">INR (₹)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
              <option value="CAD">CAD (C$)</option>
              <option value="AUD">AUD (A$)</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Base Salary (annual)</label>
            <input className={inputClass} type="number" min="0" value={salaryBase} onChange={(e) => setSalaryBase(e.target.value)} placeholder="120000" />
          </div>
          <div>
            <label className={labelClass}>Annual Bonus</label>
            <input className={inputClass} type="number" min="0" value={salaryBonus} onChange={(e) => setSalaryBonus(e.target.value)} placeholder="15000" />
          </div>
          <div>
            <label className={labelClass}>Annual RSU / Equity</label>
            <input className={inputClass} type="number" min="0" value={salaryRsu} onChange={(e) => setSalaryRsu(e.target.value)} placeholder="25000" />
          </div>
        </div>
        {ctc > 0 && (
          <div className="rounded-lg bg-brand-50 dark:bg-brand-950 p-4 border border-brand-200 dark:border-brand-800">
            <span className="text-sm font-medium text-brand-700 dark:text-brand-300">
              Total CTC: {salaryCurrency} {ctc.toLocaleString()}
            </span>
          </div>
        )}
        <h3 className="text-lg font-medium text-[var(--foreground)] pt-2">Expected Compensation</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Expected Min ({salaryCurrency})</label>
            <input className={inputClass} type="number" min="0" value={expectedMin} onChange={(e) => setExpectedMin(e.target.value)} placeholder="150000" />
          </div>
          <div>
            <label className={labelClass}>Expected Max ({salaryCurrency})</label>
            <input className={inputClass} type="number" min="0" value={expectedMax} onChange={(e) => setExpectedMax(e.target.value)} placeholder="200000" />
          </div>
        </div>
      </div>
    );
  };

  const renderStep4 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-[var(--foreground)]">Skills</h2>
      <p className="text-sm text-[var(--muted-foreground)]">
        Add your skills as badges. Our AI will classify them into categories like Languages, Frameworks, Tools, etc.
      </p>
      <div className="flex gap-2">
        <input
          className={inputClass + " flex-1"}
          value={skillInput}
          onChange={(e) => setSkillInput(e.target.value)}
          placeholder="Type a skill and press Enter (e.g. Python, Docker, System Design)"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSkill(); } }}
        />
        <button onClick={addSkill} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          Add
        </button>
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
      {rawSkills.length > 0 && (
        <button
          onClick={classifySkillsHandler}
          disabled={classifying}
          className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {classifying ? "Classifying..." : "✨ Classify with AI"}
        </button>
      )}
      {classifiedSkills && (
        <div className="space-y-3 mt-4">
          <h3 className="text-lg font-medium text-[var(--foreground)]">Classified Skills</h3>
          {SKILL_CATEGORIES.map((cat) => {
            const skills = classifiedSkills[cat] || [];
            if (skills.length === 0) return null;
            return (
              <div key={cat}>
                <span className="text-sm font-medium text-[var(--muted-foreground)]">{cat}</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {skills.map((s) => (
                    <span key={s} className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${CATEGORY_COLORS[cat]}`}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderStep5 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-[var(--foreground)]">Job Preferences</h2>
      <p className="text-sm text-[var(--muted-foreground)]">What kind of roles are you looking for?</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Target Roles (comma-separated)</label>
          <input className={inputClass} value={targetRoles} onChange={(e) => setTargetRoles(e.target.value)} placeholder="SDE 2, Backend Engineer, Platform Engineer" />
        </div>
        <div>
          <label className={labelClass}>Preferred Technologies</label>
          <input className={inputClass} value={prefTech} onChange={(e) => setPrefTech(e.target.value)} placeholder="Python, Go, Kubernetes" />
        </div>
        <div>
          <label className={labelClass}>Preferred Companies</label>
          <input className={inputClass} value={prefCompanies} onChange={(e) => setPrefCompanies(e.target.value)} placeholder="Google, Stripe, OpenAI" />
        </div>
        <div>
          <label className={labelClass}>Preferred Location</label>
          <input className={inputClass} value={prefLocation} onChange={(e) => setPrefLocation(e.target.value)} placeholder="San Francisco, Remote" />
        </div>
        <div>
          <label className={labelClass}>Search Keywords</label>
          <input className={inputClass} value={searchKeywords} onChange={(e) => setSearchKeywords(e.target.value)} placeholder="software engineer, full stack developer" />
        </div>
        <div>
          <label className={labelClass}>Remote Preference</label>
          <select className={selectClass} value={remotePref} onChange={(e) => setRemotePref(e.target.value)}>
            <option value="any">Any</option>
            <option value="remote">Remote Only</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>Job Type</label>
          <select className={selectClass} value={jobTypePref} onChange={(e) => setJobTypePref(e.target.value)}>
            <option value="full_time">Full Time</option>
            <option value="contract">Contract</option>
            <option value="either">Either</option>
          </select>
        </div>
        <div className="flex items-center gap-2 pt-6">
          <input type="checkbox" id="relocate" checked={relocate} onChange={(e) => setRelocate(e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
          <label htmlFor="relocate" className="text-sm text-[var(--foreground)]">Willing to relocate</label>
        </div>
      </div>
    </div>
  );

  const renderStep6 = () => (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-[var(--foreground)]">Platform Credentials</h2>
      <p className="text-sm text-[var(--muted-foreground)]">
        Connect your job platforms. LinkedIn is required. Indeed and Naukri are optional — if not provided, those platforms will be skipped.
        <span className="block mt-1 text-xs text-brand-600">🔒 All credentials are AES-256 encrypted at rest.</span>
      </p>
      {/* LinkedIn — required */}
      <div className="rounded-lg border-2 border-brand-500 bg-[var(--card)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg font-semibold text-[var(--foreground)]">LinkedIn</span>
          <span className="rounded bg-brand-100 dark:bg-brand-900 px-2 py-0.5 text-xs font-medium text-brand-700 dark:text-brand-300">Required</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Email / Username</label>
            <input className={inputClass} value={liUsername} onChange={(e) => setLiUsername(e.target.value)} placeholder="your@email.com" />
          </div>
          <div>
            <label className={labelClass}>Password</label>
            <input className={inputClass} type="password" value={liPassword} onChange={(e) => setLiPassword(e.target.value)} placeholder="••••••••" />
          </div>
        </div>
      </div>
      {/* Indeed — optional */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg font-semibold text-[var(--foreground)]">Indeed</span>
          <span className="rounded bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">Optional</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Email / Username</label>
            <input className={inputClass} value={indeedUsername} onChange={(e) => setIndeedUsername(e.target.value)} placeholder="your@email.com" />
          </div>
          <div>
            <label className={labelClass}>Password</label>
            <input className={inputClass} type="password" value={indeedPassword} onChange={(e) => setIndeedPassword(e.target.value)} placeholder="••••••••" />
          </div>
        </div>
      </div>
      {/* Naukri — optional */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg font-semibold text-[var(--foreground)]">Naukri</span>
          <span className="rounded bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">Optional</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Email / Username</label>
            <input className={inputClass} value={naukriUsername} onChange={(e) => setNaukriUsername(e.target.value)} placeholder="your@email.com" />
          </div>
          <div>
            <label className={labelClass}>Password</label>
            <input className={inputClass} type="password" value={naukriPassword} onChange={(e) => setNaukriPassword(e.target.value)} placeholder="••••••••" />
          </div>
        </div>
      </div>
    </div>
  );

  const renderStep7 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-[var(--foreground)]">Resume</h2>
      <p className="text-sm text-[var(--muted-foreground)]">
        Upload a PDF or paste LaTeX source. This becomes your master resume — all tailored versions derive from it.
        <span className="block mt-1 font-medium text-red-500">* Required — you cannot proceed without a resume.</span>
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => setResumeMode("latex")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            resumeMode === "latex"
              ? "bg-brand-600 text-white"
              : "bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--border)]"
          }`}
        >
          Paste LaTeX
        </button>
        <button
          onClick={() => setResumeMode("pdf")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            resumeMode === "pdf"
              ? "bg-brand-600 text-white"
              : "bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--border)]"
          }`}
        >
          Upload PDF
        </button>
      </div>
      {resumeMode === "latex" ? (
        <div>
          <label className={labelClass}>LaTeX Source Code</label>
          <textarea
            className={inputClass + " h-80 font-mono text-xs resize-y"}
            value={latexSource}
            onChange={(e) => setLatexSource(e.target.value)}
            placeholder={"\\documentclass[11pt]{article}\n\\usepackage[margin=1in]{geometry}\n\\begin{document}\n\n% Your resume content here\n\n\\end{document}"}
          />
          {latexSource && latexSource.includes("\\documentclass") && (
            <p className="mt-1 text-xs text-green-600">✓ Valid LaTeX detected</p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="rounded-lg border-2 border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center">
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              className="mx-auto block text-sm"
            />
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">PDF files only (max 10 MB)</p>
          </div>
          {pdfFile && !convertedLatex && (
            <button
              onClick={handlePdfUpload}
              disabled={uploading}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {uploading ? "Converting to LaTeX..." : "Upload & Convert to LaTeX"}
            </button>
          )}
          {convertedLatex && (
            <div className="space-y-2">
              <p className="text-sm text-green-600 font-medium">✓ PDF converted to LaTeX successfully!</p>
              <details className="rounded-lg border border-[var(--border)] p-3">
                <summary className="cursor-pointer text-sm font-medium text-[var(--foreground)]">Preview generated LaTeX</summary>
                <pre className="mt-2 max-h-60 overflow-auto rounded bg-[var(--muted)] p-3 text-xs font-mono">{convertedLatex.slice(0, 3000)}</pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderStep8 = () => {
    const updateEdu = (i: number, field: string, value: string) => {
      const updated = [...education];
      (updated[i] as Record<string, string>)[field] = value;
      setEducation(updated);
    };
    const addEdu = () => setEducation([...education, { degree: "", custom_degree: "", field_of_study: "", custom_field: "", institution: "", start_year: "", end_year: "", gpa: "", gpa_scale: "10", activities: "" }]);
    const removeEdu = (i: number) => setEducation(education.filter((_, j) => j !== i));

    return (
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-[var(--foreground)]">Education & Final Details</h2>
        <p className="text-sm text-[var(--muted-foreground)]">Almost done! Add your education and optional EEO information.</p>

        <div className="space-y-4">
          <h3 className="text-lg font-medium text-[var(--foreground)]">Education</h3>
          {education.map((edu, i) => (
            <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-[var(--foreground)]">Degree {i + 1}</span>
                {education.length > 1 && (
                  <button onClick={() => removeEdu(i)} className="text-red-500 hover:text-red-700 text-sm font-medium">Remove</button>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Degree *</label>
                  <select className={selectClass} value={edu.degree} onChange={(e) => updateEdu(i, "degree", e.target.value)}>
                    <option value="">Select degree...</option>
                    {(degreeChoices.length > 0 ? degreeChoices : ["BTech", "BE", "BSc", "BA", "BCom", "BCA", "BBA", "MTech", "ME", "MSc", "MA", "MCom", "MCA", "MBA", "PhD", "BS", "MS", "Diploma", "Other"]).map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  {edu.degree === "Other" && (
                    <input className={inputClass + " mt-2"} value={edu.custom_degree} onChange={(e) => updateEdu(i, "custom_degree", e.target.value)} placeholder="Enter custom degree name" />
                  )}
                </div>
                <div>
                  <label className={labelClass}>Field of Study</label>
                  <select className={selectClass} value={edu.field_of_study} onChange={(e) => updateEdu(i, "field_of_study", e.target.value)}>
                    <option value="">Select field...</option>
                    {(fieldChoices.length > 0 ? fieldChoices : ["Computer Science", "Information Technology", "Software Engineering", "Electrical Engineering", "Data Science", "Business Administration", "Other"]).map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                  {edu.field_of_study === "Other" && (
                    <input className={inputClass + " mt-2"} value={edu.custom_field} onChange={(e) => updateEdu(i, "custom_field", e.target.value)} placeholder="Enter custom field of study" />
                  )}
                </div>
                <div>
                  <label className={labelClass}>Institution *</label>
                  <input className={inputClass} value={edu.institution} onChange={(e) => updateEdu(i, "institution", e.target.value)} placeholder="MIT, IIT Delhi, Stanford..." />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className={labelClass}>Start Year</label>
                    <input className={inputClass} type="number" min="1950" max="2040" value={edu.start_year} onChange={(e) => updateEdu(i, "start_year", e.target.value)} placeholder="2018" />
                  </div>
                  <div>
                    <label className={labelClass}>End Year</label>
                    <input className={inputClass} type="number" min="1950" max="2040" value={edu.end_year} onChange={(e) => updateEdu(i, "end_year", e.target.value)} placeholder="2022" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className={labelClass}>GPA</label>
                    <input className={inputClass} type="number" step="0.01" min="0" max="10" value={edu.gpa} onChange={(e) => updateEdu(i, "gpa", e.target.value)} placeholder="8.5" />
                  </div>
                  <div>
                    <label className={labelClass}>GPA Scale</label>
                    <select className={selectClass} value={edu.gpa_scale} onChange={(e) => updateEdu(i, "gpa_scale", e.target.value)}>
                      <option value="10">/ 10</option>
                      <option value="4">/ 4.0</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          ))}
          <button onClick={addEdu} className="text-sm text-brand-600 hover:text-brand-700 font-medium">+ Add another degree</button>
        </div>

        {/* EEO */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Disability Status</label>
            <select className={selectClass} value={disability} onChange={(e) => setDisability(e.target.value)}>
              <option value="">Select...</option>
              <option value="no">No</option>
              <option value="yes">Yes</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Veteran Status</label>
            <select className={selectClass} value={veteran} onChange={(e) => setVeteran(e.target.value)}>
              <option value="">Select...</option>
              <option value="no">Not a Veteran</option>
              <option value="yes">Veteran</option>
              <option value="protected">Protected Veteran</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </div>
        </div>
        <div>
          <label className={labelClass}>Default Cover Letter</label>
          <textarea className={inputClass + " h-32 resize-y"} value={coverLetter} onChange={(e) => setCoverLetter(e.target.value)} placeholder="Write a default cover letter that can be customized per application..." />
        </div>
      </div>
    );
  };

  const renderCurrentStep = () => {
    switch (step) {
      case 1: return renderStep1();
      case 2: return renderStep2();
      case 3: return renderStep3();
      case 4: return renderStep4();
      case 5: return renderStep5();
      case 6: return renderStep6();
      case 7: return renderStep7();
      case 8: return renderStep8();
      default: return null;
    }
  };

  /* ──────────────── render ──────────────── */

  return (
    <div>
      {progressBar}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        {renderCurrentStep()}
        {error && (
          <div className="mt-4 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1}
            className="rounded-lg bg-[var(--muted)] px-5 py-2.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--border)] disabled:opacity-30"
          >
            ← Back
          </button>
          <button
            onClick={saveCurrentStep}
            disabled={saving || (step === 1 && !fullName) || (step === 6 && (!liUsername || !liPassword))}
            className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : step === 8 ? "Complete Setup ✓" : "Save & Continue →"}
          </button>
        </div>
      </div>
    </div>
  );
}
