"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";

interface MCPConnection {
  id: string;
  direction: "sender" | "receiver";
  name: string;
  endpoint_url: string | null;
  auth_config: Record<string, any>;
  status: string;
}

export default function MCPPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDirection, setNewDirection] = useState<"sender" | "receiver">("sender");
  const [newUrl, setNewUrl] = useState("");
  const [testing, setTesting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const data = await apiFetch<{ connections: MCPConnection[] }>(
        "/mcp/connections",
        { token: session.access_token }
      );
      setConnections(data.connections || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch connections");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const handleCreate = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      await apiFetch("/mcp/connections", {
        method: "POST",
        token: session.access_token,
        body: {
          name: newName,
          direction: newDirection,
          endpoint_url: newUrl || null,
        },
      });
      setShowCreate(false);
      setNewName("");
      setNewUrl("");
      setNewDirection("sender");
      fetchConnections();
    } catch (e) {
      console.error("Failed to create connection:", e);
    }
  };

  const handleTest = async (connId: string) => {
    setTesting(connId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const data = await apiFetch<{ status: string }>(
        `/mcp/connections/${connId}/test`,
        { method: "POST", token: session.access_token }
      );
      if (data.status === "connected") {
        fetchConnections();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to test connection");
    } finally {
      setTesting(null);
    }
  };

  const handleDelete = async (connId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      await apiFetch(`/mcp/connections/${connId}`, {
        method: "DELETE",
        token: session.access_token,
      });

      fetchConnections();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete connection");
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const data = await apiFetch<{ message?: string; meetings_imported?: number }>(
        "/meetings/sync",
        { method: "POST", token: session.access_token, body: { source: "google_meet" } }
      );
      setSyncResult(data.message || `Synced ${data.meetings_imported} meetings`);
    } catch (e) {
      setSyncResult(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
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
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger render={<Button />}>Add Connection</DialogTrigger>
            <DialogContent className="sm:max-w-md bg-app-card border-app-border">
              <DialogHeader>
                <DialogTitle className="font-display">New MCP Connection</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-app-text mb-1.5 block">Name</label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="My MCP Connection"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-app-text mb-1.5 block">Direction</label>
                  <div className="flex gap-2">
                    <Button
                      variant={newDirection === "sender" ? "default" : "outline"}
                      onClick={() => setNewDirection("sender")}
                      type="button"
                    >
                      Sender (Expose KB)
                    </Button>
                    <Button
                      variant={newDirection === "receiver" ? "default" : "outline"}
                      onClick={() => setNewDirection("receiver")}
                      type="button"
                    >
                      Receiver (Pull data)
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-app-text mb-1.5 block">
                    Endpoint URL (optional)
                  </label>
                  <Input
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="https://example.com/mcp"
                  />
                </div>
              </div>
              <DialogFooter showCloseButton>
                <Button onClick={handleCreate} disabled={!newName.trim()}>
                  Create Connection
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
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
            {/* Sender Tab */}
            <Card className="glow-card">
              <CardHeader>
                <CardTitle className="font-display text-lg flex items-center gap-2">
                  Sender Connections
                  <Badge variant="outline">{senderConns.length}</Badge>
                </CardTitle>
                <p className="text-sm text-app-muted">
                  Expose your knowledge base to external MCP clients
                </p>
              </CardHeader>
              <CardContent>
                {senderConns.length === 0 ? (
                  <p className="text-sm text-app-muted">No sender connections</p>
                ) : (
                  <div className="space-y-3">
                    {senderConns.map((conn) => (
                      <div
                        key={conn.id}
                        className="flex items-center justify-between p-3 bg-app-card rounded-lg border border-app-border"
                      >
                        <div>
                          <p className="text-sm font-medium text-app-text">{conn.name}</p>
                          <p className="text-xs text-app-muted font-mono">
                            {conn.endpoint_url || "No URL set"}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={conn.status === "connected" ? "default" : "secondary"}>
                            {conn.status}
                          </Badge>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleTest(conn.id)}
                            disabled={testing === conn.id}
                          >
                            {testing === conn.id ? "..." : "Test"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(conn.id)}
                          >
                            Del
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Receiver Tab */}
            <Card className="glow-card">
              <CardHeader>
                <CardTitle className="font-display text-lg flex items-center gap-2">
                  Receiver Connections
                  <Badge variant="outline">{receiverConns.length}</Badge>
                </CardTitle>
                <p className="text-sm text-app-muted">
                  Pull data from external sources into your knowledge base
                </p>
              </CardHeader>
              <CardContent>
                {receiverConns.length === 0 ? (
                  <p className="text-sm text-app-muted">No receiver connections</p>
                ) : (
                  <div className="space-y-3">
                    {receiverConns.map((conn) => (
                      <div
                        key={conn.id}
                        className="flex items-center justify-between p-3 bg-app-card rounded-lg border border-app-border"
                      >
                        <div>
                          <p className="text-sm font-medium text-app-text">{conn.name}</p>
                          <p className="text-xs text-app-muted font-mono">
                            {conn.endpoint_url || "No URL set"}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={conn.status === "connected" ? "default" : "secondary"}>
                            {conn.status}
                          </Badge>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleTest(conn.id)}
                            disabled={testing === conn.id}
                          >
                            {testing === conn.id ? "..." : "Test"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(conn.id)}
                          >
                            Del
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Google Meet Sync */}
        <Card className="glow-card mt-8">
          <CardHeader>
            <CardTitle className="font-display text-lg">Google Meet Sync</CardTitle>
            <p className="text-sm text-app-muted">
              Pull meeting transcripts into the knowledge base via MCP receiver
            </p>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Button onClick={handleSync} disabled={syncing}>
                {syncing ? "Syncing..." : "Sync Meetings"}
              </Button>
              {syncResult && (
                <p className="text-sm text-app-muted">{syncResult}</p>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
