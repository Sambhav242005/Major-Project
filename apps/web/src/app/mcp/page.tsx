"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
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
  const supabase = createClient();
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDirection, setNewDirection] = useState<"sender" | "receiver">("sender");
  const [newUrl, setNewUrl] = useState("");
  const [testing, setTesting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/mcp/connections", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setConnections(data.connections || []);
      }
    } catch (e) {
      console.error("Failed to fetch connections:", e);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const handleCreate = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/mcp/connections", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newName,
          direction: newDirection,
          endpoint_url: newUrl || null,
        }),
      });

      if (res.ok) {
        setShowCreate(false);
        setNewName("");
        setNewUrl("");
        fetchConnections();
      }
    } catch (e) {
      console.error("Failed to create connection:", e);
    }
  };

  const handleTest = async (connId: string) => {
    setTesting(connId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(`http://localhost:8000/mcp/connections/${connId}/test`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      const data = await res.json();
      if (data.status === "connected") {
        fetchConnections();
      }
    } catch (e) {
      console.error("Failed to test connection:", e);
    } finally {
      setTesting(null);
    }
  };

  const handleDelete = async (connId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      await fetch(`http://localhost:8000/mcp/connections/${connId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      fetchConnections();
    } catch (e) {
      console.error("Failed to delete connection:", e);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/meetings/sync", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ source: "google_meet" }),
      });

      const data = await res.json();
      setSyncResult(data.message || `Synced ${data.meetings_imported} meetings`);
    } catch (e) {
      setSyncResult("Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const senderConns = connections.filter((c) => c.direction === "sender");
  const receiverConns = connections.filter((c) => c.direction === "receiver");

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-slate hover:text-ink transition-colors">
              ← Dashboard
            </Link>
            <h1 className="font-display text-xl font-semibold text-ink">
              MCP Connections
            </h1>
          </div>
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
            <form action="/auth/signout" method="post">
              <button type="submit" className="text-sm text-rust hover:underline">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <p className="text-slate">
            Configure MCP (Model Context Protocol) connections to share knowledge with external tools
          </p>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger render={<Button />}>Add Connection</DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-display">New MCP Connection</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div>
                  <label className="text-sm font-medium text-ink mb-1 block">Name</label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="My MCP Connection"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-ink mb-1 block">Direction</label>
                  <div className="flex gap-2">
                    <Button
                      variant={newDirection === "sender" ? "default" : "outline"}
                      onClick={() => setNewDirection("sender")}
                    >
                      Sender (Expose KB)
                    </Button>
                    <Button
                      variant={newDirection === "receiver" ? "default" : "outline"}
                      onClick={() => setNewDirection("receiver")}
                    >
                      Receiver (Pull data)
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-ink mb-1 block">
                    Endpoint URL (optional)
                  </label>
                  <Input
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="https://example.com/mcp"
                  />
                </div>
                <Button onClick={handleCreate} disabled={!newName.trim()} className="w-full">
                  Create Connection
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate">Loading connections...</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Sender Tab */}
            <Card>
              <CardHeader>
                <CardTitle className="font-display text-lg flex items-center gap-2">
                  Sender Connections
                  <Badge variant="outline">{senderConns.length}</Badge>
                </CardTitle>
                <p className="text-sm text-slate">
                  Expose your knowledge base to external MCP clients
                </p>
              </CardHeader>
              <CardContent>
                {senderConns.length === 0 ? (
                  <p className="text-sm text-slate">No sender connections</p>
                ) : (
                  <div className="space-y-3">
                    {senderConns.map((conn) => (
                      <div
                        key={conn.id}
                        className="flex items-center justify-between p-3 bg-paper rounded-lg border border-slate/10"
                      >
                        <div>
                          <p className="text-sm font-medium text-ink">{conn.name}</p>
                          <p className="text-xs text-slate font-mono">
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
            <Card>
              <CardHeader>
                <CardTitle className="font-display text-lg flex items-center gap-2">
                  Receiver Connections
                  <Badge variant="outline">{receiverConns.length}</Badge>
                </CardTitle>
                <p className="text-sm text-slate">
                  Pull data from external sources into your knowledge base
                </p>
              </CardHeader>
              <CardContent>
                {receiverConns.length === 0 ? (
                  <p className="text-sm text-slate">No receiver connections</p>
                ) : (
                  <div className="space-y-3">
                    {receiverConns.map((conn) => (
                      <div
                        key={conn.id}
                        className="flex items-center justify-between p-3 bg-paper rounded-lg border border-slate/10"
                      >
                        <div>
                          <p className="text-sm font-medium text-ink">{conn.name}</p>
                          <p className="text-xs text-slate font-mono">
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
        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="font-display text-lg">Google Meet Sync</CardTitle>
            <p className="text-sm text-slate">
              Pull meeting transcripts into the knowledge base via MCP receiver
            </p>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Button onClick={handleSync} disabled={syncing}>
                {syncing ? "Syncing..." : "Sync Meetings"}
              </Button>
              {syncResult && (
                <p className="text-sm text-slate">{syncResult}</p>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
