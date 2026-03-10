"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/authStore";
import { oauthApi } from "@/lib/api";
import toast from "react-hot-toast";
import { FiArrowLeft } from "react-icons/fi";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register, isAuthenticated } = useAuthStore();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("register") === "true") {
      setIsRegister(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password, fullName);
        toast.success("Account created!");
      } else {
        await login(email, password);
        toast.success("Welcome back!");
      }
      router.push("/dashboard");
    } catch {
      toast.error(isRegister ? "Registration failed" : "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: "google" | "github") => {
    setOauthLoading(provider);
    try {
      const redirectUri = `${window.location.origin}/login/callback/${provider}`;
      const getUrl =
        provider === "google" ? oauthApi.getGoogleUrl : oauthApi.getGithubUrl;
      const { data } = await getUrl(redirectUri);
      window.location.href = data.url;
    } catch {
      toast.error(
        `${provider === "google" ? "Google" : "GitHub"} login is not configured yet`
      );
      setOauthLoading(null);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
      <div className="w-full max-w-md space-y-8 px-4">
        {/* Back to home */}
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <FiArrowLeft className="h-4 w-4" /> Back to home
        </Link>

        {/* Brand */}
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white text-2xl font-bold">
            HP
          </div>
          <h1 className="text-3xl font-bold text-[var(--foreground)]">
            {isRegister ? "Create Account" : "Welcome Back"}
          </h1>
          <p className="mt-2 text-[var(--muted-foreground)]">
            {isRegister
              ? "Start automating your job search"
              : "Sign in to your HirePilot account"}
          </p>
        </div>

        {/* OAuth Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => handleOAuth("google")}
            disabled={!!oauthLoading}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            {oauthLoading === "google" ? "Redirecting..." : "Continue with Google"}
          </button>
          <button
            onClick={() => handleOAuth("github")}
            disabled={!!oauthLoading}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
            </svg>
            {oauthLoading === "github" ? "Redirecting..." : "Continue with GitHub"}
          </button>
        </div>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[var(--border)]" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-[var(--background)] px-2 text-[var(--muted-foreground)]">
              or continue with email
            </span>
          </div>
        </div>

        {/* Email/Password Form */}
        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
                  Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="input"
                  placeholder="John Doe"
                />
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="input"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full"
            >
              {loading
                ? "Please wait..."
                : isRegister
                ? "Create Account"
                : "Sign In"}
            </button>
          </form>

          <div className="mt-4 text-center text-sm text-[var(--muted-foreground)]">
            {isRegister
              ? "Already have an account?"
              : "Don't have an account?"}{" "}
            <button
              onClick={() => setIsRegister(!isRegister)}
              className="font-medium text-brand-600 hover:underline"
            >
              {isRegister ? "Sign in" : "Sign up"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
