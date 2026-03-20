import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// ---------- Request interceptor: attach JWT ----------
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ---------- Response interceptor: handle 401 ----------
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem("refresh_token");
        if (refresh) {
          const { data } = await axios.post(`${API_BASE}/api/v1/auth/refresh`, {
            refresh_token: refresh,
          });
          localStorage.setItem("access_token", data.access_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        }
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------- Auth ----------
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  profile: () => api.get("/auth/me"),
  updateProfile: (data: Record<string, unknown>) =>
    api.patch("/auth/me", data),
  deleteAccount: () => api.delete("/auth/me"),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post("/auth/change-password", data),
  // Credentials
  getCredentials: () => api.get("/auth/credentials"),
  saveCredential: (data: { platform: string; username: string; password: string }) =>
    api.post("/auth/credentials", data),
  deleteCredential: (platform: string) =>
    api.delete(`/auth/credentials/${platform}`),
  // Preferences
  getPreferences: () => api.get("/auth/preferences"),
  updatePreferences: (data: {
    job_search_keywords?: string;
    preferred_location?: string;
    target_roles?: string[];
    preferred_technologies?: string[];
    preferred_companies?: string[];
    experience_level?: string;
    email_for_outreach?: string;
    willing_to_relocate?: boolean;
    remote_preference?: string;
    job_type_preference?: string;
  }) => api.put("/auth/preferences", data),
};

// ---------- OAuth ----------
export const oauthApi = {
  getGoogleUrl: (redirect_uri: string) =>
    api.get("/oauth/google/url", { params: { redirect_uri } }),
  googleCallback: (code: string, redirect_uri: string) =>
    api.post("/oauth/google/callback", { code, redirect_uri }),
  getGithubUrl: (redirect_uri: string) =>
    api.get("/oauth/github/url", { params: { redirect_uri } }),
  githubCallback: (code: string, redirect_uri: string) =>
    api.post("/oauth/github/callback", { code, redirect_uri }),
};

// ---------- Jobs ----------
export const jobsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/jobs", { params }),
  get: (id: string) => api.get(`/jobs/${id}`),
  delete: (id: string) => api.delete(`/jobs/${id}`),
  triggerSearch: (data: { filters: Record<string, unknown>; sources?: string[] }) =>
    api.post("/jobs/search", data),
  searchLinkedIn: (data: { filters: Record<string, unknown>; sources?: string[] }) =>
    api.post("/jobs/search-linkedin", data),
  getMatchScore: (id: string) => api.get(`/jobs/${id}/match-score`),
  topMatches: (params?: { min_score?: number; limit?: number }) =>
    api.get("/jobs/top-matches", { params }),
  scrapeUrl: (data: { url: string; resume_id?: string }) =>
    api.post("/jobs/scrape-url", data),
};

// ---------- Resumes ----------
export const resumesApi = {
  list: () => api.get("/resumes"),
  get: (id: string) => api.get(`/resumes/${id}`),
  create: (data: { name: string; latex_source: string; is_master?: boolean }) =>
    api.post("/resumes", data),
  update: (id: string, data: { name?: string; latex_source?: string }) =>
    api.patch(`/resumes/${id}`, data),
  delete: (id: string) => api.delete(`/resumes/${id}`),
  compile: (id: string) => api.post(`/resumes/${id}/compile`),
  compilePreview: (latex_source: string) =>
    api.post("/resumes/compile-preview", { latex_source }, { responseType: "blob" }),
  tailor: (data: { job_listing_id: string; base_resume_id?: string }) =>
    api.post("/resumes/tailor", data),
  templates: () => api.get("/resumes/templates"),
  getMaster: () => api.get("/resumes/master"),
  // AI Chat
  chat: (data: { resume_id: string; message: string; history?: Array<{ role: string; content: string }> }) =>
    api.post("/resumes/chat", data),
  // Parse
  parse: (id: string) => api.post(`/resumes/${id}/parse`),
  // Version diff
  diff: (versionAId: string, versionBId: string) =>
    api.get(`/resumes/diff/${versionAId}/${versionBId}`),
  // Rollback
  rollback: (data: { target_version_id: string }) =>
    api.post("/resumes/rollback", data),
  // ATS Score
  atsScore: (data: { resume_id?: string; job_id?: string; job_description?: string }) =>
    api.post("/resumes/ats-score", data),
};

// ---------- Applications ----------
export const applicationsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/applications", { params }),
  get: (id: string) => api.get(`/applications/${id}`),
  create: (data: Record<string, unknown>) =>
    api.post("/applications", data),
  delete: (id: string) => api.delete(`/applications/${id}`),
  updateStatus: (id: string, data: { status: string; notes?: string }) =>
    api.patch(`/applications/${id}/status`, data),
  analytics: () => api.get("/applications/analytics"),
  autoApply: (id: string, data: { job_listing_id: string; resume_version_id: string }) =>
    api.post(`/applications/${id}/apply`, data),
  getResume: (applicationId: string) =>
    api.get(`/applications/${applicationId}/resume`),

  // ── Apply Wizard ──
  wizardStart: (data: { job_listing_id: string }) =>
    api.post("/applications/wizard/start", data),
  wizardTailor: (jobListingId: string, data: { wizard_id: string; base_resume_id?: string }) =>
    api.post(`/applications/wizard/tailor?job_listing_id=${jobListingId}`, data),
  wizardChat: (data: {
    wizard_id: string;
    message: string;
    current_latex: string;
    history?: Array<{ role: string; content: string }>;
  }) => api.post("/applications/wizard/chat", data),
  wizardApprove: (data: {
    wizard_id: string;
    job_listing_id: string;
    final_latex: string;
    resume_name?: string;
  }) => api.post("/applications/wizard/approve", data),
  wizardApply: (data: { application_id: string }) =>
    api.post("/applications/wizard/apply", data),
};

// ---------- Insights ----------
export const insightsApi = {
  skills: () => api.get("/insights/skills"),
  hiringTrends: () => api.get("/insights/hiring-trends"),
  salaryAnalysis: () => api.get("/insights/salary-analysis"),
};

// ---------- Profile (Work Experience & Education) ----------
export const profileApi = {
  // Work Experience
  listExperiences: () => api.get("/profile/work-experience"),
  createExperience: (data: Record<string, unknown>) =>
    api.post("/profile/work-experience", data),
  updateExperience: (id: string, data: Record<string, unknown>) =>
    api.put(`/profile/work-experience/${id}`, data),
  deleteExperience: (id: string) =>
    api.delete(`/profile/work-experience/${id}`),
  bulkSaveExperiences: (data: Record<string, unknown>[]) =>
    api.put("/profile/work-experience", data),
  // Education
  getEducationChoices: () => api.get("/profile/education/choices"),
  listEducations: () => api.get("/profile/education"),
  createEducation: (data: Record<string, unknown>) =>
    api.post("/profile/education", data),
  updateEducation: (id: string, data: Record<string, unknown>) =>
    api.put(`/profile/education/${id}`, data),
  deleteEducation: (id: string) =>
    api.delete(`/profile/education/${id}`),
  bulkSaveEducations: (data: Record<string, unknown>[]) =>
    api.put("/profile/education", data),
};

// ---------- Subscription ----------
export const subscriptionApi = {
  getPlans: () => api.get("/subscription/plans"),
  getCurrent: () => api.get("/subscription/current"),
  changePlan: (plan: string) =>
    api.post("/subscription/change-plan", { plan }),
  mockPayment: (card_last4: string) =>
    api.post("/subscription/mock-payment", { card_last4 }),
  checkFeature: (feature: string) =>
    api.get(`/subscription/check-feature/${feature}`),
};

// ---------- Orchestrator ----------
export const orchestratorApi = {
  run: (data: Record<string, unknown>) =>
    api.post("/orchestrator/run", data),
  getStatus: (pipelineId: string) =>
    api.get(`/orchestrator/status/${pipelineId}`),
};

// ---------- Onboarding ----------
export const onboardingApi = {
  getProgress: () => api.get("/onboarding/progress"),
  saveStep: (step: number, data: Record<string, unknown>) =>
    api.post(`/onboarding/step/${step}`, data),
  classifySkills: (skills: string[]) =>
    api.post("/onboarding/classify-skills", { skills }),
  uploadResume: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/onboarding/upload-resume", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  getSummary: () => api.get("/onboarding/summary"),
};

// ---------- Agents ----------
export const agentsApi = {
  list: () => api.get("/agents"),
  status: () => api.get("/agents/status"),
  run: (name: string, params?: Record<string, unknown>) =>
    api.post(`/agents/${name}/run`, { params: params || {} }),
  toggle: (name: string) =>
    api.post(`/agents/${name}/toggle`, {}),
  pipeline: (agents: string[]) =>
    api.post("/agents/pipeline", { agents }),
  history: (params?: { agent_name?: string; limit?: number }) =>
    api.get("/agents/history", { params }),
};

// ---------- Emails ----------
export const emailsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/agents/history", { params: { agent_name: "email_checker", ...params } }),
};

// ---------- Salary Negotiator ----------
export const salaryNegotiatorApi = {
  chat: (data: { message: string; context?: Record<string, unknown>; history?: Array<{ role: string; content: string }> }) =>
    api.post("/agents/salary_negotiator/run", data),
};

// ---------- Recruiters ----------
export const recruitersApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/recruiters", { params }),
  get: (id: string) => api.get(`/recruiters/${id}`),
  find: (data: { company: string; role?: string }) =>
    api.post("/recruiters/find", data),
  delete: (id: string) => api.delete(`/recruiters/${id}`),
  sendOutreach: (id: string, data: { message_type: string; custom_message?: string; job_listing_id?: string }) =>
    api.post(`/recruiters/${id}/outreach`, data),
  getMessages: (id: string) => api.get(`/recruiters/${id}/messages`),
  getAllMessages: (params?: { page?: number; page_size?: number }) =>
    api.get("/recruiters/messages/all", { params }),
  generateMessage: (data: { recruiter_id: string; job_listing_id?: string; message_type?: string; tone?: string }) =>
    api.post("/recruiters/generate-message", data),
  // LinkedIn direct access
  testLinkedIn: () => api.get("/recruiters/linkedin/test"),
  fetchLinkedInInbox: (count?: number) =>
    api.get("/recruiters/linkedin/inbox", { params: { count: count || 5 } }),
};

// ---------- Trash ----------
export const trashApi = {
  list: (params?: { item_type?: string; skip?: number; limit?: number }) =>
    api.get("/trash", { params }),
  restore: (itemType: string, itemId: string) =>
    api.post(`/trash/${itemType}/${itemId}/restore`),
  permanentDelete: (itemType: string, itemId: string) =>
    api.delete(`/trash/${itemType}/${itemId}`),
  empty: () => api.delete("/trash"),
};

export default api;
