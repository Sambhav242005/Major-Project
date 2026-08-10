"use client";

import { useEffect, useState, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard-header";
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
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loadError, setLoadError] = useState(false);
  const supabaseRef = useRef(createClient());

  useEffect(() => {
    let cancelled = false;
    const supabase = supabaseRef.current;

    async function fetchDashboard() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session || cancelled) return;

        const json = await apiFetch<{ status: string; data: DashboardData }>(
          "/dashboard/summary",
          { token: session.access_token }
        );
        if (json.status === "ok" && !cancelled) {
          setData(json.data);
          setLoadError(false);
          setLastUpdated(new Date());
        }
      } catch (e) {
        console.error("Failed to fetch dashboard:", e);
        if (!cancelled) setLoadError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const stats = data ? [
    { label: "Processed", value: data.documents.processed, color: "text-emerald-600 dark:text-emerald-400" },
    { label: "Processing", value: data.documents.processing, color: "text-amber dark:text-amber" },
    { label: "Failed", value: data.documents.failed, color: "text-red-600 dark:text-red-400" },
    { label: "Entities", value: data.total_entities, color: "text-sky-600 dark:text-sky-400" },
    { label: "Relationships", value: data.total_relationships, color: "text-purple-600 dark:text-purple-400" },
    { label: "Chat Sessions", value: data.total_chats, color: "text-app-muted" },
    { label: "Active Agents", value: data.active_agents, color: "text-emerald-600 dark:text-emerald-400" },
  ] : [];

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="AI Knowledge Graph Builder" />

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="font-display text-2xl font-semibold text-app-text mb-1">
            Dashboard
          </h2>
          <p className="text-app-muted text-sm">
            Overview of your knowledge base and pipeline status
            {lastUpdated && !loading && (
              <span className="text-app-muted/70 ml-2">
                · Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10" role="status" aria-label="Loading dashboard">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-app-card border border-app-border p-4 animate-pulse">
                <div className="h-3 bg-app-surface-alt rounded w-20 mb-3" />
                <div className="h-6 bg-app-surface-alt rounded w-12" />
              </div>
            ))}
          </div>
        ) : !data ? (
          <div className="text-center py-12">
            <p className="text-red-600 dark:text-red-400 mb-4">Failed to load dashboard</p>
            <button
              onClick={() => { setLoading(true); setLoadError(false); window.location.reload(); }}
              className="px-4 py-2 bg-brand-accent/15 text-app-text font-medium rounded-lg hover:bg-brand-accent/25 transition-colors text-sm"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              {stats.map((stat) => (
                <div key={stat.label} className="bg-app-card border border-app-border p-4">
                  <p className="text-xs text-app-muted uppercase tracking-wider mb-1">{stat.label}</p>
                  <p className={`text-2xl font-semibold font-mono ${stat.color}`}>
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
              <Card className="bg-app-card border border-app-border">
                <CardHeader>
                  <CardTitle className="font-display text-lg text-app-text">Pipeline Health</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-app-muted">Success Rate</span>
                      <span className={`font-mono font-semibold ${
                        data.pipeline_health.success_rate >= 90 ? "text-emerald-600 dark:text-emerald-400" :
                        data.pipeline_health.success_rate >= 70 ? "text-amber dark:text-amber" : "text-red-600 dark:text-red-400"
                      }`}>
                        {data.pipeline_health.success_rate}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-app-muted">Queue Depth</span>
                      <span className="font-mono font-semibold text-app-text">
                        {data.pipeline_health.queue_depth}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-app-muted">Failed</span>
                      <span className={`font-mono font-semibold ${
                        data.pipeline_health.failed_count > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
                      }`}>
                        {data.pipeline_health.failed_count}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-app-card border border-app-border">
                <CardHeader>
                  <CardTitle className="font-display text-lg text-app-text">Failed Documents</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.failed_documents.length === 0 ? (
                    <p className="text-sm text-emerald-600 dark:text-emerald-400">No failures</p>
                  ) : (
                    <div className="space-y-2">
                      {data.failed_documents.map((doc) => (
                        <div key={doc.id} className="text-sm">
                          <p className="font-medium text-app-text">{doc.filename}</p>
                          <p className="text-red-600 dark:text-red-400 text-xs">{doc.error_message}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-app-card border border-app-border">
                <CardHeader>
                  <CardTitle className="font-display text-lg text-app-text">Quick Links</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Link href="/documents" className="block text-sm text-app-text hover:text-accent transition-colors">
                      Document Library →
                    </Link>
                    <Link href="/chat" className="block text-sm text-app-text hover:text-accent transition-colors">
                      Ask Questions →
                    </Link>
                    <Link href="/graph" className="block text-sm text-app-text hover:text-accent transition-colors">
                      Knowledge Graph Explorer →
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="bg-app-card border border-app-border">
              <CardHeader>
                <CardTitle className="font-display text-lg text-app-text">Recent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_activity.length === 0 ? (
                  <p className="text-sm text-app-muted">No activity yet</p>
                ) : (
                  <div className="space-y-2">
                    {data.recent_activity.map((log) => (
                      <div key={log.id} className="flex items-center gap-3 text-sm">
                        <StatusPill status={log.action === "document.uploaded" ? "pending" : log.action === "document.processed" ? "processed" : "processing"} />
                        <span className="text-app-text">{log.resource_type}</span>
                        {log.resource_id && (
                          <span className="font-mono text-xs text-app-muted">{log.resource_id.slice(0, 8)}...</span>
                        )}
                        {log.created_at && (
                          <span className="text-xs text-app-muted ml-auto">
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
