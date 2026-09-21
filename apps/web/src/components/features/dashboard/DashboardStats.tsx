"use client";

import { FileText, GitBranch, Database, MessageSquare, Bot } from "lucide-react";

interface DashboardStatsProps {
  totalDocuments: number;
  totalEntities: number;
  totalRelationships: number;
  totalChats: number;
  activeAgents: number;
}

export function DashboardStats({
  totalDocuments,
  totalEntities,
  totalRelationships,
  totalChats,
  activeAgents,
}: DashboardStatsProps) {
  const stats = [
    { label: "Documents", value: totalDocuments, icon: FileText, color: "text-sky-400" },
    { label: "Entities", value: totalEntities, icon: Database, color: "text-emerald-400" },
    { label: "Relationships", value: totalRelationships, icon: GitBranch, color: "text-amber-400" },
    { label: "Chats", value: totalChats, icon: MessageSquare, color: "text-purple-400" },
    { label: "Active Agents", value: activeAgents, icon: Bot, color: "text-cyan-400" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="glow-card p-4 text-center">
          <s.icon size={20} className={`mx-auto mb-2 ${s.color}`} />
          <p className="text-xl font-bold text-app-text">{s.value}</p>
          <p className="text-[10px] text-app-muted mt-0.5">{s.label}</p>
        </div>
      ))}
    </div>
  );
}
