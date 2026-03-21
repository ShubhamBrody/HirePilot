import { create } from "zustand";
import { authApi } from "@/lib/api";

interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  headline: string | null;
  summary: string | null;
  skills: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  job_search_keywords: string | null;
  preferred_location: string | null;
  target_roles: string | null;
  preferred_technologies: string | null;
  preferred_companies: string | null;
  experience_level: string | null;
  email_for_outreach: string | null;
  is_active: boolean;
  is_verified: boolean;
  // Onboarding fields
  onboarding_completed: boolean;
  onboarding_step: number;
  current_company: string | null;
  current_title: string | null;
  years_of_experience: number | null;
  salary_currency: string | null;
  current_salary_ctc: number | null;
  expected_salary_min: number | null;
  expected_salary_max: number | null;
  classified_skills: Record<string, string[]> | null;
  remote_preference: string | null;
  willing_to_relocate: boolean | null;
  job_type_preference: string | null;
  // Company search fields
  auto_apply_threshold: number | null;
  company_search_enabled: boolean;
  linkedin_search_enabled: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password) => {
    const { data } = await authApi.login({ email, password });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    // Fetch user profile after login
    const profileRes = await authApi.profile();
    set({ user: profileRes.data, isAuthenticated: true });
  },

  register: async (email, password, full_name) => {
    const { data } = await authApi.register({ email, password, full_name });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    // Fetch user profile after registration
    const profileRes = await authApi.profile();
    set({ user: profileRes.data, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false });
    window.location.href = "/login";
  },

  loadUser: async () => {
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        set({ isLoading: false });
        return;
      }
      const { data } = await authApi.profile();
      set({ user: data, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  refreshUser: async () => {
    try {
      const { data } = await authApi.profile();
      set({ user: data });
    } catch {
      // silently ignore
    }
  },
}));
