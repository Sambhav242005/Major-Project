"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/StatusPill";

interface DashboardData {
  documents: { pending: number; processing: number; processed: number; failed: number };
  total_documents: number;
  total_entities: number;
  total_relationships: number;
  total_chats: number;
  active_agents: number;
  recent_activity: {
    id: string;
    action: string;
    resource_type: string;
    resource_id: string | null;
    created_at: string | null;
  }[];
  failed_documents: {
    id: string;
    filename: string;
    error_message: string | null;
    uploaded_at: string | null;
  }[];
  pipeline_health: {
    queue_depth: number;
    failed_count: number;
    success_rate: number;
  };
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const supabase = createClient();

  const fetchDashboard = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/dashboard/summary", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const json = await res.json();
        if (json.status === "ok") {
          setData(json.data);
        }
      }
    } catch (e) {
      console.error("Failed to fetch dashboard:", e);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Poll every 10s for live updates
  useEffect(() => {
    const interval = setInterval(fetchDashboard, 10000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const stats = data ? [
    { label: "Processed", value: data.documents.processed, color: "text-verified" },
    { label: "Processing", value: data.documents.processing, color: "text-amber" },
    { label: "Failed", value: data.documents.failed, color: "text-rust" },
    { label: "Entities", value: data.total_entities, color: "text-ink" },
    { label: "Relationships", value: data.total_relationships, color: "text-ink" },
    { label: "Chat Sessions", value: data.total_chats, color: "text-slate" },
    { label: "Active Agents", value: data.active_agents, color: "text-verified" },
    { label: "Queue Depth", value: data.pipeline_health.queue_depth, color: "text-amber" },
  ] : [];

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="font-display text-xl font-semibold text-ink">
            AI Knowledge Graph Builder
          </h1>
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-sm text-slate hover:text-ink transition-colors">
              Documents
            </Link>
            <Link href="/chat" className="text-sm text-slate hover:text-ink transition-colors">
              Chat
            </Link>
            <Link href="/graph" className="text-sm text-slate hover:text-ink transition-colors">
              Graph
            </Link>
            <Link href="/agents" className="text-sm text-slate hover:text-ink transition-colors">
              Agents
            </Link>
            <Link href="/mcp" className="text-sm text-slate hover:text-ink transition-colors">
              MCP
            </Link>
            <form action="/auth/signout" method="post">
              <button type="submit" className="text-sm text-rust hover:underline">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="font-display text-2xl font-semibold text-ink mb-1">
            Dashboard
          </h2>
          <p className="text-slate">
            Overview of your knowledge base and pipeline status
          </p>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate">Loading dashboard...</div>
        ) : !data ? (
          <div className="text-center py-12 text-rust">Failed to load dashboard</div>
        ) : (
          <>
            {/* Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              {stats.map((stat) => (
                <div key={stat.label} className="bg-white rounded-lg border border-slate/20 p-4">
                  <p className="text-sm text-slate mb-1">{stat.label}</p>
                  <p className={`text-2xl font-semibold font-mono ${stat.color}`}>
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
              {/* Pipeline Health */}
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-lg">Pipeline Health</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-slate">Success Rate</span>
                      <span className={`font-mono font-semibold ${
                        data.pipeline_health.success_rate >= 90 ? "text-verified" :
                        data.pipeline_health.success_rate >= 70 ? "text-amber" : "text-rust"
                      }`}>
                        {data.pipeline_health.success_rate}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-slate">Queue Depth</span>
                      <span className="font-mono font-semibold text-ink">
                        {data.pipeline_health.queue_depth}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-slate">Failed</span>
                      <span className={`font-mono font-semibold ${
                        data.pipeline_health.failed_count > 0 ? "text-rust" : "text-verified"
                      }`}>
                        {data.pipeline_health.failed_count}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Failed Documents */}
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-lg">Failed Documents</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.failed_documents.length === 0 ? (
                    <p className="text-sm text-verified">No failures</p>
                  ) : (
                    <div className="space-y-2">
                      {data.failed_documents.map((doc) => (
                        <div key={doc.id} className="text-sm">
                          <p className="font-medium text-ink">{doc.filename}</p>
                          <p className="text-rust text-xs">{doc.error_message}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Quick Links */}
              <Card>
                <CardHeader>
                  <CardTitle className="font-display text-lg">Quick Links</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Link href="/documents" className="block text-sm text-ink hover:text-amber transition-colors">
                      Document Library →
                    </Link>
                    <Link href="/chat" className="block text-sm text-ink hover:text-amber transition-colors">
                      Ask Questions →
                    </Link>
                    <Link href="/graph" className="block text-sm text-ink hover:text-amber transition-colors">
                      Knowledge Graph Explorer →
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Activity Feed */}
            <Card>
              <CardHeader>
                <CardTitle className="font-display text-lg">Recent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_activity.length === 0 ? (
                  <p className="text-sm text-slate">No activity yet</p>
                ) : (
                  <div className="space-y-2">
                    {data.recent_activity.map((log) => (
                      <div key={log.id} className="flex items-center gap-3 text-sm">
                        <StatusPill status={log.action === "document.uploaded" ? "pending" : log.action === "document.processed" ? "processed" : "processing"} />
                        <span className="text-ink">{log.resource_type}</span>
                        {log.resource_id && (
                          <span className="font-mono text-xs text-slate">{log.resource_id.slice(0, 8)}...</span>
                        )}
                        {log.created_at && (
                          <span className="text-xs text-slate ml-auto">
                            {new Date(log.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
