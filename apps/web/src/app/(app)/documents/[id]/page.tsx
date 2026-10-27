"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, withProject } from "@/lib/api/client";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MediaPreview } from "@/components/features/documents/MediaPreview";
import { sourceLabel, type SourceLocation } from "@/lib/source-location";
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
  source_location?: SourceLocation | null;
  text: string;
  text_truncated: boolean;
  token_count: number | null;
}

interface Entity {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "tag-amber",
  ORG: "tag-green",
  GPE: "tag-cyan",
  EVENT: "tag-red",
  CONCEPT: "tag-purple",
};

export default function DocumentDetailPage() {
  const params = useParams();
  const documentId = params.id as string;
  const { activeProjectId } = useProjectStore();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [supabase] = useState(() => createClient());

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const token = session.access_token;

      const [docData, chunksData, entitiesData] = await Promise.all([
        apiFetch<DocumentDetail>(`/documents/${documentId}`, { token, projectId: activeProjectId }),
        apiFetch<{ data: Chunk[] }>(`/documents/${documentId}/chunks`, { token, projectId: activeProjectId }),
        apiFetch<{ data: Entity[] }>(`/documents/${documentId}/entities`, { token, projectId: activeProjectId }),
      ]);

      setDoc(docData);
      setChunks(chunksData.data || []);
      setEntities(entitiesData.data || []);
      setErrorMsg(null);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [documentId, activeProjectId, supabase.auth]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll status if pending/failed — a stuck doc needs a chance to update
  useEffect(() => {
    if (!doc || (doc.status !== "pending" && doc.status !== "processing")) return;
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [doc, fetchData]);

  const handleRetry = async () => {
    setRetrying(true);
    setErrorMsg(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Your session expired. Sign in again.");

      // A replacement is optional: the API can retry the saved private original.
      const file = fileInputRef.current?.files?.[0];
      let res: Response;
      try {
        const formData = new FormData();
        if (file) formData.append("file", file);

        res = await fetch(
          withProject(`/documents/${documentId}/retry`, activeProjectId),
          {
            method: "POST",
            headers: { Authorization: `Bearer ${session.access_token}` },
            body: formData,
          }
        );
      } catch {
        throw new Error("Cannot reach the server. Check that the backend is running and try again.");
      }
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Retry failed");
      }

      // Poll until status changes
      await fetchData();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-app-bg text-app-text flex items-center justify-center">
        <p className="text-app-muted">Loading document...</p>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="min-h-screen bg-app-bg text-app-text flex items-center justify-center">
        <p role="alert" className="text-red-600 dark:text-red-400">{errorMsg || "Document not found"}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title={doc.filename} showBack backHref="/documents" />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {errorMsg && <p role="alert" className="mb-4 text-sm text-red-400">{errorMsg}</p>}
        {doc.file_type.startsWith("audio/") || doc.file_type.startsWith("video/") ? <MediaPreview key={`${activeProjectId}:${documentId}`} documentId={documentId} projectId={activeProjectId} fileType={doc.file_type} chunks={chunks} /> : null}
        {/* Document Info */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="stat-glow p-4">
            <p className="text-sm text-slate-500 mb-1">Type</p>
            <p className="font-mono text-sm text-app-text">
              {doc.file_type.split("/").pop()?.toUpperCase()}
            </p>
          </div>
          <div className="stat-glow p-4">
            <p className="text-sm text-slate-500 mb-1">Pages</p>
            <p className="font-mono text-sm text-app-text">{doc.page_count ?? "—"}</p>
          </div>
          <div className="stat-glow p-4">
            <p className="text-sm text-slate-500 mb-1">Chunks</p>
            <p className="font-mono text-sm text-app-text">{chunks.length}</p>
          </div>
          <div className="stat-glow p-4">
            <p className="text-sm text-slate-500 mb-1">Entities</p>
            <p className="font-mono text-sm text-app-text">{entities.length}</p>
          </div>
          <div className="stat-glow p-4">
            <p className="text-sm text-slate-500 mb-1">Uploaded</p>
            <p className="text-sm text-app-text">
              {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : "—"}
            </p>
          </div>
        </div>

        {/* Error + Retry — show for failed AND stale pending docs */}
        {(doc.error_message || doc.status === "pending" || doc.status === "failed") && (
          <Card className="mb-8 border-amber-400/30 glow-card border-0">
            <CardContent className="py-4 flex items-center justify-between gap-4 flex-wrap">
              <div>
                <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
                  {doc.error_message ? "Processing Error" : doc.status === "pending" ? "Waiting to process" : "Processing failed"}
                </p>
                <p className="text-sm text-app-muted">
                  {doc.error_message ?? (doc.status === "pending" ? "Queued for processing. Status refreshes automatically." : "Processing failed. Retry the saved original, or select a replacement.")}
                </p>
                {errorMsg && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{errorMsg}</p>}
              </div>
              {doc.status === "failed" && <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  className="text-sm text-app-muted"
                  aria-label="Choose file to retry"
                />
                <Button
                  onClick={handleRetry}
                  disabled={retrying}
                  variant="outline"
                  className="border-amber-400/30 text-amber-600 dark:text-amber-400 hover:bg-amber-400/10"
                >
                  {retrying ? "Retrying..." : "Retry Processing"}
                </Button>
              </div>}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chunks */}
          <Card className="glow-card border-0">
            <CardHeader>
              <CardTitle className="font-display text-lg">
                Chunks ({chunks.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {chunks.length === 0 ? (
                <p className="text-sm text-app-muted">No chunks yet</p>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="bg-app-card rounded-lg p-3 border border-app-border"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          #{chunk.chunk_index}
                        </Badge>
                        {chunk.source_location && <a href={`#t=${chunk.source_location.start_seconds}`} className="text-xs underline text-brand-accent">{sourceLabel(chunk.source_location)}</a>}
                        {chunk.page_number && (
                          <Badge variant="outline" className="text-xs">
                            Page {chunk.page_number}
                          </Badge>
                        )}
                        {chunk.token_count && (
                          <span className="text-xs text-app-muted font-mono">
                            {chunk.token_count} tokens
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-app-text leading-relaxed">{chunk.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Entities */}
          <Card className="glow-card border-0">
            <CardHeader>
              <CardTitle className="font-display text-lg">
                Extracted Entities ({entities.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {entities.length === 0 ? (
                <p className="text-sm text-app-muted">No entities extracted yet</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {entities.map((entity) => (
                    <div
                      key={entity.id}
                      className="flex items-start gap-3 p-3 bg-app-card rounded-lg border border-app-border"
                    >
                      <Badge
                        className={ENTITY_COLORS[entity.type] || "tag-cyan"}
                      >
                        {entity.type}
                      </Badge>
                      <div>
                        <p className="text-sm font-medium text-app-text">{entity.name}</p>
                        {entity.description && (
                          <p className="text-xs text-app-muted mt-0.5">{entity.description}</p>
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
