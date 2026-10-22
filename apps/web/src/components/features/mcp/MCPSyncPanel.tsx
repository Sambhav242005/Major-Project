"use client";
import Link from "next/link";
import { Calendar } from "lucide-react";

export function MCPSyncPanel() {
  return <div className="glow-card p-4 space-y-3">
    <div className="flex items-center gap-2"><Calendar size={16} /><h3 className="text-sm font-medium">Meeting import</h3></div>
    <p className="text-xs text-app-muted">Automatic Google Meet import is unavailable. Record or upload audio for manual transcription and analysis.</p>
    <Link href="/meetings" className="text-xs underline">Open Meetings</Link>
  </div>;
}
