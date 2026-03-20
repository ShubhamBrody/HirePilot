"use client";

import { useCallback, useEffect, useState } from "react";
import { subscriptionApi } from "@/lib/api";
import toast from "react-hot-toast";

interface Plan {
  name: string;
  price_monthly: number;
  max_resumes: number;
  max_applications_per_day: number;
  max_job_scrapes_per_day: number;
  ai_tailoring_enabled: boolean;
  recruiter_outreach_enabled: boolean;
  autonomous_mode_enabled: boolean;
}

interface Sub {
  plan: string;
  status: string;
  price_monthly: number;
  billing_cycle: string;
  mock_card_last4: string | null;
  mock_next_billing_date: string | null;
  ai_tailoring_enabled: boolean;
  recruiter_outreach_enabled: boolean;
  autonomous_mode_enabled: boolean;
}

export default function SubscriptionPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [current, setCurrent] = useState<Sub | null>(null);
  const [loading, setLoading] = useState(true);
  const [changing, setChanging] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, currentRes] = await Promise.all([
        subscriptionApi.getPlans(),
        subscriptionApi.getCurrent(),
      ]);
      setPlans(plansRes.data.plans);
      setCurrent(currentRes.data);
    } catch {
      toast.error("Failed to load subscription info");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleChangePlan = async (plan: string) => {
    setChanging(plan);
    try {
      const { data } = await subscriptionApi.changePlan(plan);
      setCurrent(data);
      toast.success(`Switched to ${plan} plan`);
    } catch {
      toast.error("Failed to change plan");
    } finally {
      setChanging(null);
    }
  };

  const limit = (v: number) => (v === -1 ? "Unlimited" : String(v));

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Subscription & Billing</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Manage your plan and billing preferences.
        </p>
      </div>

      {/* Current Plan Banner */}
      {current && (
        <div className="rounded-lg border border-brand-500/30 bg-brand-50 dark:bg-brand-950/20 p-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-[var(--muted-foreground)]">Current Plan</p>
            <p className="text-lg font-bold text-[var(--foreground)] capitalize">{current.plan}</p>
            <p className="text-sm text-[var(--muted-foreground)]">
              {current.price_monthly === 0
                ? "Free forever"
                : `$${current.price_monthly}/mo`}
              {current.mock_card_last4 && ` · Card ending ${current.mock_card_last4}`}
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              current.status === "active"
                ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                : "bg-red-100 text-red-800"
            }`}
          >
            {current.status}
          </span>
        </div>
      )}

      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((plan) => {
          const isCurrent = current?.plan === plan.name;
          const highlight = plan.name === "pro";
          return (
            <div
              key={plan.name}
              className={`rounded-xl border p-6 flex flex-col ${
                highlight
                  ? "border-brand-500 shadow-lg shadow-brand-500/10"
                  : "border-[var(--border)]"
              } bg-[var(--card)]`}
            >
              {highlight && (
                <span className="self-start rounded-full bg-brand-600 px-3 py-0.5 text-xs font-medium text-white mb-3">
                  Most Popular
                </span>
              )}
              <h3 className="text-xl font-bold text-[var(--foreground)] capitalize">{plan.name}</h3>
              <p className="text-3xl font-bold text-[var(--foreground)] mt-2">
                {plan.price_monthly === 0 ? "Free" : `$${plan.price_monthly}`}
                {plan.price_monthly > 0 && (
                  <span className="text-sm font-normal text-[var(--muted-foreground)]">/mo</span>
                )}
              </p>

              <ul className="mt-4 space-y-2 flex-1 text-sm text-[var(--muted-foreground)]">
                <li>{limit(plan.max_resumes)} resumes</li>
                <li>{limit(plan.max_applications_per_day)} applications/day</li>
                <li>{limit(plan.max_job_scrapes_per_day)} job scrapes/day</li>
                <li className={plan.ai_tailoring_enabled ? "text-green-600 dark:text-green-400" : "line-through opacity-50"}>
                  AI resume tailoring
                </li>
                <li className={plan.recruiter_outreach_enabled ? "text-green-600 dark:text-green-400" : "line-through opacity-50"}>
                  Recruiter outreach
                </li>
                <li className={plan.autonomous_mode_enabled ? "text-green-600 dark:text-green-400" : "line-through opacity-50"}>
                  Autonomous mode
                </li>
              </ul>

              <button
                onClick={() => handleChangePlan(plan.name)}
                disabled={isCurrent || changing !== null}
                className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                  isCurrent
                    ? "bg-[var(--muted)] text-[var(--muted-foreground)] cursor-default"
                    : highlight
                    ? "bg-brand-600 text-white hover:bg-brand-700"
                    : "bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--border)]"
                } disabled:opacity-50`}
              >
                {isCurrent
                  ? "Current Plan"
                  : changing === plan.name
                  ? "Switching..."
                  : `Switch to ${plan.name}`}
              </button>
            </div>
          );
        })}
      </div>

      {/* Feature Access Summary */}
      {current && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">Feature Access</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <FeatureBadge label="AI Tailoring" enabled={current.ai_tailoring_enabled} />
            <FeatureBadge label="Recruiter Outreach" enabled={current.recruiter_outreach_enabled} />
            <FeatureBadge label="Autonomous Mode" enabled={current.autonomous_mode_enabled} />
          </div>
        </div>
      )}
    </div>
  );
}

function FeatureBadge({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className={`flex items-center gap-2 rounded-lg border p-3 ${
      enabled
        ? "border-green-500/30 bg-green-50 dark:bg-green-900/10"
        : "border-[var(--border)] bg-[var(--muted)] opacity-60"
    }`}>
      <span className={`text-lg ${enabled ? "text-green-600" : "text-[var(--muted-foreground)]"}`}>
        {enabled ? "\u2713" : "\u2717"}
      </span>
      <span className="text-[var(--foreground)] font-medium">{label}</span>
    </div>
  );
}
