"use client";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Minimal header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]">
        <div className="mx-auto flex h-14 max-w-4xl items-center px-6">
          <span className="text-lg font-bold text-brand-600">HirePilot</span>
          <span className="ml-3 text-sm text-[var(--muted-foreground)]">
            Account Setup
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}
