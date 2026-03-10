"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { oauthApi } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import toast from "react-hot-toast";

export default function GoogleCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { loadUser } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("No authorization code received");
      return;
    }

    const redirectUri = `${window.location.origin}/login/callback/google`;

    oauthApi
      .googleCallback(code, redirectUri)
      .then(({ data }) => {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        return loadUser();
      })
      .then(() => {
        toast.success("Signed in with Google!");
        router.replace("/dashboard");
      })
      .catch(() => {
        setError("Google sign-in failed. Please try again.");
      });
  }, [searchParams, router, loadUser]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
        <div className="text-center space-y-4">
          <p className="text-red-500 font-medium">{error}</p>
          <button
            onClick={() => router.push("/login")}
            className="btn-primary"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
        <p className="text-sm text-[var(--muted-foreground)]">
          Completing Google sign-in...
        </p>
      </div>
    </div>
  );
}
