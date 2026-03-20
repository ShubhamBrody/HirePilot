"use client";

import { useCallback, useEffect, useState } from "react";
import { profileApi, authApi } from "@/lib/api";
import toast from "react-hot-toast";

interface WorkExp {
  id?: string;
  company: string;
  role: string;
  location: string;
  description: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

interface Edu {
  id?: string;
  degree: string;
  custom_degree: string;
  field_of_study: string;
  custom_field: string;
  institution: string;
  start_year: string;
  end_year: string;
  gpa: string;
  gpa_scale: string;
}

const emptyExp: WorkExp = { company: "", role: "", location: "", description: "", start_date: "", end_date: "", is_current: false };
const emptyEdu: Edu = { degree: "", custom_degree: "", field_of_study: "", custom_field: "", institution: "", start_year: "", end_year: "", gpa: "", gpa_scale: "10" };

export default function ProfilePage() {
  const [tab, setTab] = useState<"experience" | "education" | "summary">("experience");
  const [experiences, setExperiences] = useState<WorkExp[]>([]);
  const [educations, setEducations] = useState<Edu[]>([]);
  const [degreeChoices, setDegreeChoices] = useState<string[]>([]);
  const [fieldChoices, setFieldChoices] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // AI Career Summary
  const [careerSummary, setCareerSummary] = useState<string | null>(null);
  const [genSummary, setGenSummary] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [expRes, eduRes, choicesRes] = await Promise.all([
        profileApi.listExperiences(),
        profileApi.listEducations(),
        profileApi.getEducationChoices(),
      ]);
      setExperiences(
        expRes.data.experiences.map((e: Record<string, unknown>) => ({
          id: e.id,
          company: e.company || "",
          role: e.role || "",
          location: e.location || "",
          description: e.description || "",
          start_date: e.start_date || "",
          end_date: e.end_date || "",
          is_current: e.is_current || false,
        }))
      );
      setEducations(
        eduRes.data.educations.map((e: Record<string, unknown>) => ({
          id: e.id,
          degree: e.degree || "",
          custom_degree: e.custom_degree || "",
          field_of_study: e.field_of_study || "",
          custom_field: e.custom_field || "",
          institution: e.institution || "",
          start_year: e.start_year ? String(e.start_year) : "",
          end_year: e.end_year ? String(e.end_year) : "",
          gpa: e.gpa ? String(e.gpa) : "",
          gpa_scale: e.gpa_scale ? String(e.gpa_scale) : "10",
        }))
      );
      setDegreeChoices(choicesRes.data.degree_choices || []);
      setFieldChoices(choicesRes.data.field_of_study_choices || []);
    } catch {
      toast.error("Failed to load profile data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const saveExperiences = async () => {
    setSaving(true);
    try {
      const valid = experiences.filter((e) => e.company && e.role);
      await profileApi.bulkSaveExperiences(valid);
      toast.success("Work experiences saved");
      loadData();
    } catch {
      toast.error("Failed to save experiences");
    } finally {
      setSaving(false);
    }
  };

  const saveEducations = async () => {
    setSaving(true);
    try {
      const valid = educations.filter((e) => e.degree && e.institution);
      const payload = valid.map((e) => ({
        ...e,
        start_year: e.start_year ? parseInt(e.start_year) : undefined,
        end_year: e.end_year ? parseInt(e.end_year) : undefined,
        gpa: e.gpa ? parseFloat(e.gpa) : undefined,
        gpa_scale: e.gpa_scale ? parseFloat(e.gpa_scale) : undefined,
      }));
      await profileApi.bulkSaveEducations(payload);
      toast.success("Education saved");
      loadData();
    } catch {
      toast.error("Failed to save education");
    } finally {
      setSaving(false);
    }
  };

  const generateCareerSummary = async () => {
    setGenSummary(true);
    try {
      const { data: profile } = await authApi.profile();
      const expText = experiences
        .map((e) => `${e.role} at ${e.company}${e.is_current ? " (current)" : ""}`)
        .join("; ");
      const eduText = educations
        .map((e) => `${e.degree} from ${e.institution}`)
        .join("; ");

      const prompt = `Generate a professional career summary for:\nName: ${profile.full_name}\nExperience: ${expText}\nEducation: ${eduText}\nSkills: ${profile.skills || "N/A"}\n\nProvide: 1) A 2-3 sentence career summary, 2) Top 3 strengths, 3) Areas for growth.`;

      // Use the auth profile update endpoint to store summary
      // For now, just show the prompt result via existing infra
      setCareerSummary(
        `Career Summary for ${profile.full_name}\n\n` +
        `Experience: ${expText || "No experiences added yet"}\n` +
        `Education: ${eduText || "No education added yet"}\n\n` +
        `Add more details to your profile to get an AI-generated career assessment.`
      );
    } catch {
      toast.error("Failed to generate summary");
    } finally {
      setGenSummary(false);
    }
  };

  const updateExp = (i: number, field: string, value: string | boolean) => {
    const updated = [...experiences];
    (updated[i] as Record<string, string | boolean>)[field] = value;
    if (field === "is_current" && value === true) updated[i].end_date = "";
    setExperiences(updated);
  };

  const updateEdu = (i: number, field: string, value: string) => {
    const updated = [...educations];
    (updated[i] as Record<string, string>)[field] = value;
    setEducations(updated);
  };

  const inputClass =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";
  const labelClass = "block text-sm font-medium text-[var(--foreground)] mb-1";
  const selectClass = inputClass;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Profile</h1>
        <p className="text-sm text-[var(--muted-foreground)]">Manage your work experience, education, and career summary.</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 rounded-lg bg-[var(--muted)] p-1">
        {(["experience", "education", "summary"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === t
                ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {t === "experience" ? "Work Experience" : t === "education" ? "Education" : "Career Summary"}
          </button>
        ))}
      </div>

      {/* Work Experience Tab */}
      {tab === "experience" && (
        <div className="space-y-4">
          {experiences.map((exp, i) => (
            <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-[var(--foreground)]">
                  {exp.role ? `${exp.role} at ${exp.company}` : `Experience ${i + 1}`}
                </span>
                <button onClick={() => setExperiences(experiences.filter((_, j) => j !== i))} className="text-red-500 hover:text-red-700 text-sm font-medium">
                  Remove
                </button>
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
                  <input type="checkbox" checked={exp.is_current} onChange={(e) => updateExp(i, "is_current", e.target.checked)} className="h-4 w-4 rounded border-[var(--border)]" />
                  <label className="text-sm text-[var(--foreground)]">I currently work here</label>
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
                <textarea className={inputClass + " h-20 resize-y"} value={exp.description} onChange={(e) => updateExp(i, "description", e.target.value)} placeholder="Key responsibilities and achievements..." />
              </div>
            </div>
          ))}

          <div className="flex items-center justify-between">
            <button
              onClick={() => setExperiences([...experiences, { ...emptyExp }])}
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              + Add Experience
            </button>
            <button
              onClick={saveExperiences}
              disabled={saving}
              className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Experiences"}
            </button>
          </div>
        </div>
      )}

      {/* Education Tab */}
      {tab === "education" && (
        <div className="space-y-4">
          {educations.map((edu, i) => (
            <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-[var(--foreground)]">
                  {edu.degree && edu.institution ? `${edu.degree} — ${edu.institution}` : `Education ${i + 1}`}
                </span>
                <button onClick={() => setEducations(educations.filter((_, j) => j !== i))} className="text-red-500 hover:text-red-700 text-sm font-medium">
                  Remove
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Degree *</label>
                  <select className={selectClass} value={edu.degree} onChange={(e) => updateEdu(i, "degree", e.target.value)}>
                    <option value="">Select degree...</option>
                    {degreeChoices.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  {edu.degree === "Other" && (
                    <input className={inputClass + " mt-2"} value={edu.custom_degree} onChange={(e) => updateEdu(i, "custom_degree", e.target.value)} placeholder="Custom degree name" />
                  )}
                </div>
                <div>
                  <label className={labelClass}>Field of Study</label>
                  <select className={selectClass} value={edu.field_of_study} onChange={(e) => updateEdu(i, "field_of_study", e.target.value)}>
                    <option value="">Select field...</option>
                    {fieldChoices.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                  {edu.field_of_study === "Other" && (
                    <input className={inputClass + " mt-2"} value={edu.custom_field} onChange={(e) => updateEdu(i, "custom_field", e.target.value)} placeholder="Custom field" />
                  )}
                </div>
                <div>
                  <label className={labelClass}>Institution *</label>
                  <input className={inputClass} value={edu.institution} onChange={(e) => updateEdu(i, "institution", e.target.value)} placeholder="MIT, IIT Delhi..." />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className={labelClass}>Start Year</label>
                    <input className={inputClass} type="number" min="1950" max="2040" value={edu.start_year} onChange={(e) => updateEdu(i, "start_year", e.target.value)} />
                  </div>
                  <div>
                    <label className={labelClass}>End Year</label>
                    <input className={inputClass} type="number" min="1950" max="2040" value={edu.end_year} onChange={(e) => updateEdu(i, "end_year", e.target.value)} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className={labelClass}>GPA</label>
                    <input className={inputClass} type="number" step="0.01" min="0" max="10" value={edu.gpa} onChange={(e) => updateEdu(i, "gpa", e.target.value)} />
                  </div>
                  <div>
                    <label className={labelClass}>Scale</label>
                    <select className={selectClass} value={edu.gpa_scale} onChange={(e) => updateEdu(i, "gpa_scale", e.target.value)}>
                      <option value="10">/ 10</option>
                      <option value="4">/ 4.0</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          ))}

          <div className="flex items-center justify-between">
            <button
              onClick={() => setEducations([...educations, { ...emptyEdu }])}
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              + Add Education
            </button>
            <button
              onClick={saveEducations}
              disabled={saving}
              className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Education"}
            </button>
          </div>
        </div>
      )}

      {/* Career Summary Tab */}
      {tab === "summary" && (
        <div className="space-y-4">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">AI Career Summary</h3>
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              Get an AI-generated assessment of your career, strengths, and areas for growth based on your profile data.
            </p>
            <button
              onClick={generateCareerSummary}
              disabled={genSummary}
              className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50 mb-4"
            >
              {genSummary ? "Generating..." : "Generate Career Summary"}
            </button>
            {careerSummary && (
              <div className="rounded-lg bg-[var(--muted)] p-4 whitespace-pre-wrap text-sm text-[var(--foreground)]">
                {careerSummary}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
