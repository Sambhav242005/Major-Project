"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useMCP } from "@/hooks/useMCP";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { MCPConnectionCard } from "@/components/features/mcp";
import { MCPCreateDialog } from "@/components/features/mcp";
import { MCPSyncPanel } from "@/components/features/mcp";
import type { MCPConnectionRaw } from "@/lib/types";

export default function MCPPage() {
  const { activeProjectId } = useProjectStore();
  const { token } = useAuth();
  const { connections, loading, error, createConnection, updateConnection, deleteConnection, syncConnection, syncMeetings } = useMCP({ token, projectId: activeProjectId });
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncingMeetings, setSyncingMeetings] = useState(false);

  const handleCreate = async (direction: "sender" | "receiver", name: string) => {
    await createConnection({ name, endpoint_url: "", auth_config: { direction } });
  };

  const handleUpdate = async (id: string, data: Partial<MCPConnectionRaw>) => {
    await updateConnection(id, data);
  };

  const handleDelete = async (id: string) => {
    await deleteConnection(id);
  };

  const handleSyncConnection = async (connectionId: string) => {
    setSyncingId(connectionId);
    try {
      await syncConnection(connectionId);
    } finally {
      setSyncingId(null);
    }
  };

  const handleSyncMeetings = async () => {
    setSyncingMeetings(true);
    try {
      await syncMeetings();
    } finally {
      setSyncingMeetings(false);
    }
  };

  const senderConns = connections.filter((c) => c.direction === "sender");
  const receiverConns = connections.filter((c) => c.direction === "receiver");

  return (
    <div className="min-h-screen bg-app-bg">
      <DashboardHeader title="MCP Connections" showBack backHref="/dashboard" />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <p className="text-app-muted">
            Configure MCP (Model Context Protocol) connections to share knowledge with external tools
          </p>
          <MCPCreateDialog onCreate={handleCreate} />
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 text-app-muted">Loading connections...</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-medium text-app-text mb-3">Sender ({senderConns.length})</h3>
              <div className="space-y-3">
                {senderConns.length === 0 ? (
                  <p className="text-xs text-app-muted">No sender connections</p>
                ) : senderConns.map((conn) => (
                  <MCPConnectionCard
                    key={conn.id}
                    connection={conn}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    onSync={handleSyncConnection}
                    isSyncing={syncingId === conn.id}
                  />
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-sm font-medium text-app-text mb-3">Receiver ({receiverConns.length})</h3>
              <div className="space-y-3">
                {receiverConns.length === 0 ? (
                  <p className="text-xs text-app-muted">No receiver connections</p>
                ) : receiverConns.map((conn) => (
                  <MCPConnectionCard
                    key={conn.id}
                    connection={conn}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    onSync={handleSyncConnection}
                    isSyncing={syncingId === conn.id}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="mt-8">
          <MCPSyncPanel onSync={handleSyncMeetings} isSyncing={syncingMeetings} />
        </div>
      </main>
    </div>
  );
}
