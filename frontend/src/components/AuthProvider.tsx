"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

const PUBLIC_ROUTES = ["/", "/login"];
const ONBOARDING_ROUTES = ["/onboarding"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (isLoading) return;

    const isPublic =
      PUBLIC_ROUTES.includes(pathname) ||
      pathname.startsWith("/login/callback");
    const isOnboarding = ONBOARDING_ROUTES.some((r) => pathname.startsWith(r));

    if (!isAuthenticated && !isPublic) {
      router.replace("/login");
      return;
    }

    // If authenticated user visits landing or login, redirect appropriately
    if (isAuthenticated && (pathname === "/login" || pathname === "/")) {
      if (user && !user.onboarding_completed) {
        router.replace("/onboarding");
      } else {
        router.replace("/dashboard");
      }
      return;
    }

    // Enforce onboarding completion for app routes
    if (isAuthenticated && user && !user.onboarding_completed && !isOnboarding && !isPublic) {
      router.replace("/onboarding");
      return;
    }

    // If onboarding is done and user navigates to /onboarding, send to dashboard
    if (isAuthenticated && user?.onboarding_completed && isOnboarding) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, pathname, router, user]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--background)]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
