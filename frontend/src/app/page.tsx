"use client";

import Link from "next/link";
import {
  FiBriefcase,
  FiFileText,
  FiSend,
  FiUsers,
  FiZap,
  FiShield,
  FiArrowRight,
} from "react-icons/fi";

const features = [
  {
    icon: FiBriefcase,
    title: "Smart Job Discovery",
    description:
      "AI-powered scraping across LinkedIn, Indeed, and Naukri. Automatically find and rank jobs that match your skills.",
  },
  {
    icon: FiFileText,
    title: "Resume Tailoring",
    description:
      "GPT-powered LaTeX resume customization. Tailor your resume for each job listing with one click.",
  },
  {
    icon: FiSend,
    title: "Auto-Apply Bot",
    description:
      "Automated job applications via headless browser. Apply to hundreds of jobs while you sleep.",
  },
  {
    icon: FiUsers,
    title: "Recruiter Outreach",
    description:
      "Find and connect with recruiters at target companies. AI-generated personalized messages.",
  },
  {
    icon: FiZap,
    title: "Application Tracking",
    description:
      "Full pipeline view from applied to offer. Track status, interviews, and follow-ups in one place.",
  },
  {
    icon: FiShield,
    title: "Secure & Private",
    description:
      "AES-256 encrypted credentials, JWT authentication, and full audit logging. Your data stays safe.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Navbar */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white font-bold text-sm">
              HP
            </div>
            <span className="text-xl font-bold text-[var(--foreground)]">
              HirePilot
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/login?register=true"
              className="btn-primary text-sm"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 py-24 text-center">
        <div className="mx-auto max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-4 py-1.5 text-sm font-medium text-brand-700 dark:border-brand-800 dark:bg-brand-900/20 dark:text-brand-400">
            <FiZap className="h-4 w-4" />
            AI-Powered Job Search Automation
          </div>
          <h1 className="text-5xl font-extrabold tracking-tight text-[var(--foreground)] sm:text-6xl">
            Land Your Dream Job{" "}
            <span className="text-brand-600">10x Faster</span>
          </h1>
          <p className="mt-6 text-lg text-[var(--muted-foreground)] leading-relaxed">
            HirePilot automates your entire job search — from discovering opportunities
            and tailoring resumes to applying automatically and connecting with recruiters.
            Let AI do the heavy lifting while you focus on interviews.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <Link
              href="/login?register=true"
              className="btn-primary inline-flex items-center gap-2 px-8 py-3 text-base"
            >
              Start Free <FiArrowRight className="h-5 w-5" />
            </Link>
            <Link
              href="/login"
              className="btn-secondary inline-flex items-center gap-2 px-8 py-3 text-base"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-[var(--border)] bg-[var(--muted)]">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-[var(--foreground)]">
              Everything You Need to Automate Your Job Search
            </h2>
            <p className="mt-3 text-[var(--muted-foreground)]">
              Six powerful modules working together to supercharge your career hunt.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, description }) => (
              <div key={title} className="card hover:shadow-lg transition-shadow">
                <div className="mb-4 inline-flex items-center justify-center rounded-xl bg-brand-50 p-3 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-[var(--foreground)]">
                  {title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">
                  {description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--border)]">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold text-[var(--foreground)]">
            Ready to Accelerate Your Job Search?
          </h2>
          <p className="mt-3 text-[var(--muted-foreground)]">
            Join HirePilot and let AI handle the busywork.
          </p>
          <Link
            href="/login?register=true"
            className="btn-primary mt-8 inline-flex items-center gap-2 px-10 py-3 text-base"
          >
            Create Your Account <FiArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] bg-[var(--card)]">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-xs">
                HP
              </div>
              <span className="text-sm font-semibold text-[var(--foreground)]">
                HirePilot
              </span>
            </div>
            <p className="text-xs text-[var(--muted-foreground)]">
              &copy; {new Date().getFullYear()} HirePilot. Built with AI.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
