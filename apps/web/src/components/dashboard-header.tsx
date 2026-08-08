"use client";

import Link from "next/link";
import dynamic from "next/dynamic";

const StatusIndicator = dynamic(
  () => import("@/components/status-indicator").then((m) => m.StatusIndicator),
  { ssr: false }
);

const NAV_LINKS = [
  { href: "/documents", label: "Documents" },
  { href: "/chat", label: "Chat" },
  { href: "/graph", label: "Graph" },
  { href: "/agents", label: "Agents" },
  { href: "/mcp", label: "MCP" },
  { href: "/webhooks", label: "Webhooks" },
];

interface DashboardHeaderProps {
  title: string;
  showBack?: boolean;
  backHref?: string;
}

export function DashboardHeader({ title, showBack = false, backHref = "/dashboard" }: DashboardHeaderProps) {
  return (
    <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {showBack && (
            <Link href={backHref} className="text-sm text-slate hover:text-ink transition-colors">
              ← Back
            </Link>
          )}
          <h1 className="font-display text-xl font-semibold text-ink">
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-slate hover:text-ink transition-colors"
            >
              {link.label}
            </Link>
          ))}
          <StatusIndicator />
          <form action="/auth/signout" method="post">
            <button type="submit" className="text-sm text-rust hover:underline">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
