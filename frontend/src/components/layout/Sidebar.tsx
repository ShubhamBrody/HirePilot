"use client";

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
} from "react-icons/fi";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";

const navItems = [
  { href: "/", label: "Dashboard", icon: FiHome },
  { href: "/jobs", label: "Jobs", icon: FiBriefcase },
  { href: "/resumes", label: "Resumes", icon: FiFileText },
  { href: "/applications", label: "Applications", icon: FiSend },
  { href: "/recruiters", label: "Recruiters", icon: FiUsers },
  { href: "/settings", label: "Settings", icon: FiSettings },
];

export function Sidebar() {
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);

  return (
    <aside className="flex h-full w-64 flex-col border-r border-[var(--border)] bg-[var(--card)]">
      {/* Brand */}
      <div className="flex h-16 items-center gap-2 px-6 border-b border-[var(--border)]">
        <div className="h-8 w-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm">
          HP
        </div>
        <span className="text-lg font-bold text-[var(--foreground)]">
          HirePilot
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              )}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="border-t border-[var(--border)] p-4">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--muted-foreground)] hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/10 transition-colors"
        >
          <FiLogOut className="h-5 w-5" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
