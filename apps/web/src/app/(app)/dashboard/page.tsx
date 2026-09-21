"use client";

import { DashboardHeader } from "@/components/layout/dashboard-header";
import { DashboardStats } from "@/components/features/dashboard";
import { PipelineHealthCard } from "@/components/features/dashboard";
import { FailedDocsCard } from "@/components/features/dashboard";
import { RecentActivityCard } from "@/components/features/dashboard";
import { QuickLinksCard } from "@/components/features/dashboard";
import { useAuth } from "@/hooks/useAuth";
import { useDashboard } from "@/hooks/useDashboard";
import { useProjectStore } from "@/stores/project";

export default function DashboardPage() {
  const { activeProjectId } = useProjectStore();
  const { token } = useAuth();
  const { data, loading, error: loadError, refresh } = useDashboard({ token, projectId: activeProjectId, pollInterval: 10000 });

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
              onClick={() => refresh()}
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
