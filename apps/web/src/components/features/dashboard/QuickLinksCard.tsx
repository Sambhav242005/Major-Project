"use client";

import Link from "next/link";
import { FileText, GitBranch, MessageSquare } from "lucide-react";

export function QuickLinksCard() {
  const links = [
    { href: "/documents", label: "Upload Documents", icon: FileText },
    { href: "/graph", label: "Explore Graph", icon: GitBranch },
    { href: "/chat", label: "Start Chatting", icon: MessageSquare },
  ];

  return (
    <div className="glow-card p-4">
      <h3 className="text-sm font-medium text-app-text mb-3">Quick Links</h3>
      <div className="space-y-2">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-center gap-2 text-xs text-app-muted hover:text-sky-400 transition-colors"
          >
            <link.icon size={14} />
            {link.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
