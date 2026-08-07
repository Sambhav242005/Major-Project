"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/StatusPill";
import { Badge } from "@/components/ui/badge";

interface DocumentDetail {
  id: string;
  filename: string;
  file_type: string;
  status: string;
  page_count: number | null;
  error_message: string | null;
  uploaded_at: string | null;
  processed_at: string | null;
}

interface Chunk {
  id: string;
  chunk_index: number;
  page_number: number | null;
  text: string;
  token_count: number | null;
}

interface Entity {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "bg-amber/10 text-amber",
  ORG: "bg-verified/10 text-verified",
  GPE: "bg-slate/10 text-slate",
  EVENT: "bg-rust/10 text-rust",
  CONCEPT: "bg-ink/10 text-ink",
};

export default function DocumentDetailPage() {
  const params = useParams();
  const documentId = params.id as string;
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const supabase = createClient();

  const fetchData = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const headers = { Authorization: `Bearer ${session.access_token}` };

      const [docRes, chunksRes, entitiesRes] = await Promise.all([
        fetch(`http://localhost:8000/documents/${documentId}`, { headers }),
        fetch(`http://localhost:8000/documents/${documentId}/chunks`, { headers }),
        fetch(`http://localhost:8000/documents/${documentId}/entities`, { headers }),
      ]);

      if (docRes.ok) setDoc(await docRes.json());
      if (chunksRes.ok) {
        const data = await chunksRes.json();
        setChunks(data.data || []);
      }
      if (entitiesRes.ok) {
        const data = await entitiesRes.json();
        setEntities(data.data || []);
      }
    } catch (e) {
      console.error("Failed to fetch document:", e);
    } finally {
      setLoading(false);
    }
  }, [documentId, supabase]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll status if processing
  useEffect(() => {
    if (!doc || (doc.status !== "pending" && doc.status !== "processing")) return;
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [doc, fetchData]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      await fetch(`http://localhost:8000/documents/${documentId}/retry`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      // Poll until status changes
      setTimeout(fetchData, 2000);
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <p className="text-slate">Loading document...</p>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <p className="text-rust">Document not found</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/documents" className="text-sm text-slate hover:text-ink transition-colors">
            ← Back
          </Link>
          <h1 className="font-display text-xl font-semibold text-ink truncate">
            {doc.filename}
          </h1>
          <StatusPill status={doc.status} />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Document Info */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="bg-white rounded-lg border border-slate/20 p-4">
            <p className="text-sm text-slate mb-1">Type</p>
            <p className="font-mono text-sm text-ink">
              {doc.file_type.split("/").pop()?.toUpperCase()}
            </p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-4">
            <p className="text-sm text-slate mb-1">Pages</p>
            <p className="font-mono text-sm text-ink">{doc.page_count ?? "—"}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-4">
            <p className="text-sm text-slate mb-1">Chunks</p>
            <p className="font-mono text-sm text-ink">{chunks.length}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-4">
            <p className="text-sm text-slate mb-1">Entities</p>
            <p className="font-mono text-sm text-ink">{entities.length}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-4">
            <p className="text-sm text-slate mb-1">Uploaded</p>
            <p className="text-sm text-ink">
              {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : "—"}
            </p>
          </div>
        </div>

        {/* Error + Retry */}
        {doc.error_message && (
          <Card className="mb-8 border-rust/30">
            <CardContent className="py-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-rust">Processing Error</p>
                <p className="text-sm text-slate">{doc.error_message}</p>
              </div>
              <Button
                onClick={handleRetry}
                disabled={retrying}
                variant="outline"
                className="border-rust/30 text-rust hover:bg-rust/10"
              >
                {retrying ? "Retrying..." : "Retry Processing"}
              </Button>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chunks */}
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">
                Chunks ({chunks.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {chunks.length === 0 ? (
                <p className="text-sm text-slate">No chunks yet</p>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="bg-paper rounded-lg p-3 border border-slate/10"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          #{chunk.chunk_index}
                        </Badge>
                        {chunk.page_number && (
                          <Badge variant="outline" className="text-xs">
                            Page {chunk.page_number}
                          </Badge>
                        )}
                        {chunk.token_count && (
                          <span className="text-xs text-slate font-mono">
                            {chunk.token_count} tokens
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-ink leading-relaxed">{chunk.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Entities */}
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">
                Extracted Entities ({entities.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {entities.length === 0 ? (
                <p className="text-sm text-slate">No entities extracted yet</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {entities.map((entity) => (
                    <div
                      key={entity.id}
                      className="flex items-start gap-3 p-3 bg-paper rounded-lg border border-slate/10"
                    >
                      <Badge
                        className={ENTITY_COLORS[entity.type] || "bg-slate/10 text-slate"}
                      >
                        {entity.type}
                      </Badge>
                      <div>
                        <p className="text-sm font-medium text-ink">{entity.name}</p>
                        {entity.description && (
                          <p className="text-xs text-slate mt-0.5">{entity.description}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
