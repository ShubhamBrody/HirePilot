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
  updatePreferences: (data: { job_search_keywords?: string; preferred_location?: string }) =>
    api.put("/auth/preferences", data),
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
  triggerScrape: (data: { keywords: string[]; location?: string; sources?: string[] }) =>
    api.post("/jobs/scrape", data),
  getMatchScore: (id: string) => api.get(`/jobs/${id}/match-score`),
};

// ---------- Resumes ----------
export const resumesApi = {
  list: () => api.get("/resumes"),
  get: (id: string) => api.get(`/resumes/${id}`),
  create: (data: { name: string; latex_content: string; is_master?: boolean }) =>
    api.post("/resumes", data),
  update: (id: string, data: { name?: string; latex_content?: string }) =>
    api.put(`/resumes/${id}`, data),
  delete: (id: string) => api.delete(`/resumes/${id}`),
  compile: (id: string) => api.post(`/resumes/${id}/compile`),
  tailor: (id: string, data: { job_listing_id: string }) =>
    api.post(`/resumes/${id}/tailor`, data),
  templates: () => api.get("/resumes/templates"),
};

// ---------- Applications ----------
export const applicationsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/applications", { params }),
  get: (id: string) => api.get(`/applications/${id}`),
  create: (data: Record<string, unknown>) =>
    api.post("/applications", data),
  updateStatus: (id: string, data: { status: string; notes?: string }) =>
    api.patch(`/applications/${id}/status`, data),
  analytics: () => api.get("/applications/analytics"),
  autoApply: (data: { job_listing_id: string; resume_version_id: string }) =>
    api.post("/applications/auto-apply", data),
};

// ---------- Recruiters ----------
export const recruitersApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/recruiters", { params }),
  get: (id: string) => api.get(`/recruiters/${id}`),
  find: (data: { company: string; role?: string }) =>
    api.post("/recruiters/find", data),
  sendOutreach: (id: string, data: { message_type: string; job_title?: string }) =>
    api.post(`/recruiters/${id}/outreach`, data),
  generateMessage: (id: string, data: { message_type: string }) =>
    api.post(`/recruiters/${id}/generate-message`, data),
};

export default api;
