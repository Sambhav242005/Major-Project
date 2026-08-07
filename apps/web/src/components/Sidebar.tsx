"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/documents", label: "Documents", icon: "📄" },
  { href: "/chat", label: "Chat", icon: "💬" },
  { href: "/graph", label: "Graph", icon: "🔗" },
  { href: "/agents", label: "Agents", icon: "🤖" },
  { href: "/mcp", label: "MCP", icon: "🔌" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r border-slate/20 bg-white/50 hidden md:block">
      <nav className="p-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-amber/10 text-amber font-medium"
                  : "text-slate hover:bg-slate/5 hover:text-ink"
              )}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
