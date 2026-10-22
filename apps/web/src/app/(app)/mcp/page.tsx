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
import { API_BASE } from "@/lib/api/client";

export default function MCPPage() {
  const { activeProjectId } = useProjectStore();
  const { token } = useAuth();
  const { connections, loading, error, createConnection, updateConnection, deleteConnection, syncConnection } = useMCP({ token, projectId: activeProjectId });
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const mcpEndpoint = `${API_BASE}/mcp${activeProjectId ? `?project_id=${encodeURIComponent(activeProjectId)}` : ""}`;

  const handleCreate = async (direction: "sender" | "receiver", name: string) => {
    await createConnection({ direction, name, endpoint_url: "", auth_config: {} });
  };

  const handleUpdate = async (id: string, data: Partial<MCPConnectionRaw>) => {
    await updateConnection(id, data);
  };

  const handleDelete = async (id: string) => {
    await deleteConnection(id);
  };

  const handleSyncConnection = async (connectionId: string) => {
    setSyncingId(connectionId);
    setTestResult(null);
    try {
      const result = await syncConnection(connectionId);
      setTestResult(`MCP handshake succeeded: protocol ${result.protocol_version}, ${result.tool_count ?? "unknown"} tools advertised. Tool execution was not tested.`);
    } catch { /* hook exposes the failure; never label it successful */
    } finally {
      setSyncingId(null);
    }
  };


  const senderConns = connections.filter((c) => c.direction === "sender");
  const receiverConns = connections.filter((c) => c.direction === "receiver");

  return (
    <div className="min-h-screen bg-app-bg">
      <DashboardHeader title="MCP Connections" showBack backHref="/dashboard" />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <section className="mb-6 rounded-lg border border-app-border p-4 space-y-2 text-sm">
          <h2 className="font-medium">AKGB read-only MCP endpoint</h2>
          <code className="block break-all">{mcpEndpoint}</code>
          <button className="text-xs underline" onClick={async () => {
            try {
              await navigator.clipboard.writeText(new URL(mcpEndpoint, window.location.origin).href);
              setCopyMessage("Endpoint copied. Your bearer token is not included.");
            } catch { setCopyMessage("Clipboard permission denied. Select and copy the endpoint above."); }
          }}>Copy endpoint</button>
          {copyMessage && <p role="status" className="text-xs text-app-muted">{copyMessage}</p>}
          <p className="text-app-muted">Supports initialize, tools/list, and tools/call for search_knowledge_base, fetch_document, and get_knowledge_graph. Use an MCP client that supplies your AKGB bearer token. A browser GET is not a connection test.</p>
          <p className="text-app-muted">ChatGPT model OAuth authorizes answer generation separately. Connecting the ChatGPT website as an MCP client requires a supported authentication flow and public HTTPS; that connector setup is not provided here.</p>
        </section>
        <div className="flex items-center justify-between mb-6">
          <p className="text-app-muted">
            Configure outgoing MCP connections and test their handshake. Import and synchronization of external knowledge are not implemented.
          </p>
          <MCPCreateDialog onCreate={handleCreate} />
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}
        {testResult && <p role="status" className="mb-4 text-sm text-emerald-400">{testResult}</p>}

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
          <MCPSyncPanel />
        </div>
      </main>
    </div>
  );
}
