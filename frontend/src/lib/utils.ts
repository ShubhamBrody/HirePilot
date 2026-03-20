import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a date string for display */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Capitalize first letter */
export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

/** Truncate text to a maximum length */
export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 3) + "...";
}

/** Status color mapping for application badges */
export const statusColors: Record<string, string> = {
  draft: "badge-gray",
  applying: "badge-yellow",
  applied: "badge-blue",
  viewed: "badge-blue",
  interview: "badge-amber",
  offer: "badge-green",
  rejected: "badge-red",
  withdrawn: "badge-red",
  // Legacy aliases
  saved: "badge-gray",
  screening: "badge-yellow",
  interviewing: "badge-amber",
  accepted: "badge-green",
  no_response: "badge-gray",
};
