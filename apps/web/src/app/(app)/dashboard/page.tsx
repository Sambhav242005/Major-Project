"use client";

import { useEffect, useState, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { DashboardStats } from "@/components/features/dashboard";
import { PipelineHealthCard } from "@/components/features/dashboard";
import { FailedDocsCard } from "@/components/features/dashboard";
import { RecentActivityCard } from "@/components/features/dashboard";
import { QuickLinksCard } from "@/components/features/dashboard";
import { useProjectStore } from "@/stores/project";

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
  const [loadError, setLoadError] = useState<string | null>(null);
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const { activeProjectId } = useProjectStore();

  useEffect(() => {
    let cancelled = false;

    async function fetchDashboard() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session || cancelled) return;

        const json = await apiFetch<{ status: string; data: DashboardData }>(
          "/dashboard/summary",
          { token: session.access_token, projectId: activeProjectId }
        );
        if (json.status === "ok" && !cancelled) {
          setData(json.data);
          setLoadError(null);
          setLastUpdated(new Date());
        }
      } catch (e) {
        if (!cancelled) {
          setLoadError(
            e instanceof Error ? e.message : "Failed to load dashboard"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [activeProjectId, supabase]);

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
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-10" role="status" aria-label="Loading dashboard">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="glow-card p-4 animate-pulse">
                <div className="h-3 bg-app-surface rounded w-20 mb-3" />
                <div className="h-6 bg-app-surface rounded w-12" />
              </div>
            ))}
          </div>
        ) : !data ? (
          <div className="text-center py-12">
            <p className="text-red-400 mb-4">{loadError ?? "Failed to load dashboard"}</p>
            <button
              onClick={() => { setLoading(true); setLoadError(null); window.location.reload(); }}
              className="px-4 py-2 bg-brand-accent/15 text-app-text font-medium rounded-lg hover:bg-brand-accent/25 transition-colors text-sm"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            <DashboardStats
              totalDocuments={data.total_documents}
              totalEntities={data.total_entities}
              totalRelationships={data.total_relationships}
              totalChats={data.total_chats}
              activeAgents={data.active_agents}
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 my-10">
              <PipelineHealthCard health={data.pipeline_health} />
              <FailedDocsCard documents={data.failed_documents} onRetry={() => {}} />
              <QuickLinksCard />
            </div>

            <RecentActivityCard activities={data.recent_activity} />
          </>
        )}
      </main>
    </div>
  );
}
