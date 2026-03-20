"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FiHome,
  FiBriefcase,
  FiFileText,
  FiSend,
  FiUsers,
  FiSettings,
  FiLogOut,
  FiCpu,
  FiDollarSign,
  FiMessageSquare,
  FiTarget,
  FiTrash2,
  FiUser,
  FiZap,
} from "react-icons/fi";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { HirePilotLogo } from "@/components/HirePilotLogo";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: FiHome },
  { href: "/jobs", label: "Jobs", icon: FiBriefcase },
  { href: "/resumes", label: "Resumes", icon: FiFileText },
  { href: "/applications", label: "Applications", icon: FiSend },
  { href: "/recruiters", label: "Recruiters", icon: FiUsers },
  { href: "/profile", label: "Profile", icon: FiUser },
  { href: "/linkedin-messages", label: "Messages", icon: FiMessageSquare },
  { href: "/agents", label: "AI Agents", icon: FiCpu },
  { href: "/orchestrator", label: "Pipeline", icon: FiZap },
  { href: "/ats-score", label: "ATS Score", icon: FiTarget },
  { href: "/salary-negotiator", label: "Salary", icon: FiDollarSign },
  { href: "/subscription", label: "Billing", icon: FiDollarSign },
  { href: "/trash", label: "Trash", icon: FiTrash2 },
  { href: "/settings", label: "Settings", icon: FiSettings },
];

export function Sidebar() {
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const [hovered, setHovered] = useState(false);

  const expanded = hovered;

  return (
    <>
      {/* Collapsed rail — always visible */}
      <aside
        className={cn(
          "relative z-30 flex h-full flex-col border-r border-[var(--border)] bg-[var(--card)] transition-all duration-300 ease-in-out",
          expanded ? "w-56" : "w-[60px]"
        )}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* Brand */}
        <div className="flex h-14 items-center border-b border-[var(--border)] px-3 overflow-hidden">
          <HirePilotLogo size={30} className="shrink-0" />
          <span
            className={cn(
              "ml-2.5 text-base font-bold text-[var(--foreground)] whitespace-nowrap transition-opacity duration-200",
              expanded ? "opacity-100" : "opacity-0 w-0"
            )}
          >
            HirePilot
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-2 py-3 overflow-hidden">
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive =
              pathname === href ||
              (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                title={expanded ? undefined : label}
                className={cn(
                  "flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors whitespace-nowrap",
                  isActive
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span
                  className={cn(
                    "ml-3 transition-opacity duration-200",
                    expanded ? "opacity-100" : "opacity-0 w-0"
                  )}
                >
                  {label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="border-t border-[var(--border)] px-2 py-3">
          <button
            onClick={logout}
            title={expanded ? undefined : "Sign Out"}
            className="flex w-full items-center rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--muted-foreground)] hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/10 transition-colors whitespace-nowrap"
          >
            <FiLogOut className="h-5 w-5 shrink-0" />
            <span
              className={cn(
                "ml-3 transition-opacity duration-200",
                expanded ? "opacity-100" : "opacity-0 w-0"
              )}
            >
              Sign Out
            </span>
          </button>
        </div>
      </aside>
    </>
  );
}
