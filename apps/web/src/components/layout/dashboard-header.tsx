"use client";

import Link from "next/link";
import Image from "next/image";
import dynamic from "next/dynamic";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProjectSwitcher } from "@/components/layout/project-switcher";

const StatusIndicator = dynamic(
  () => import("@/components/status-indicator").then((m) => m.StatusIndicator),
  { ssr: false }
);

const NAV_LINKS = [
  { href: "/documents", label: "Documents" },
  { href: "/repository", label: "Repository" },
  { href: "/chat", label: "Chat" },
  { href: "/graph", label: "Graph" },
  { href: "/agents", label: "Agents" },
  { href: "/meetings", label: "Meetings" },
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
    <header className="border-b border-app-border bg-app-header-bg backdrop-blur-xl sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-y-3">
        <div className="flex items-center gap-4">
          {showBack && (
            <Link href={backHref} className="text-sm text-app-muted hover:text-app-text transition-colors">
              ← Back
            </Link>
          )}
          <Link href="/dashboard" aria-label="AKGB dashboard" className="shrink-0">
            <Image src="/icon.svg" alt="" width={30} height={30} unoptimized />
          </Link>
          <h1 className="font-display text-xl font-semibold text-app-text">
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-app-muted hover:text-app-text transition-colors"
            >
              {link.label}
            </Link>
          ))}
          <ProjectSwitcher />
          <StatusIndicator />
          <ThemeToggle />
          <form action="/auth/signout" method="post">
            <button type="submit" className="text-sm text-red-500 hover:text-red-400 transition-colors">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
