"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api/client";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DashboardHeader } from "@/components/dashboard-header";
import { StatusPill } from "@/components/StatusPill";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocumentListSchema, type Document } from "@/lib/validators";
import Link from "next/link";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingDoc, setProcessingDoc] = useState<string | null>(null);
  const [processStage, setProcessStage] = useState<string>("");
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const data = await apiFetch<{ documents: any[] }>("/documents", {
        token: session.access_token,
      });

      const docs = (data.documents || []).map((d: any) => ({
        id: d.id,
        filename: d.filename,
        fileType: d.file_type,
        status: d.status,
        pageCount: d.page_count,
        chunkCount: d.chunk_count,
        errorMessage: d.error_message,
        uploadedAt: d.uploaded_at,
        processedAt: d.processed_at,
      }));
      const parsed = DocumentListSchema.safeParse({ documents: docs });
      if (parsed.success) {
        setDocuments(parsed.data.documents);
      } else {
        console.error("Invalid response:", parsed.error);
        setDocuments(docs);
      }
    } catch (e) {
      console.error("Failed to fetch documents:", e);
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Track the doc we're currently watching for live progress. Set
  // immediately on upload so the progress bar shows right away, and also
  // derived from the list for docs pending from a previous load.
  const [watchingDocId, setWatchingDocId] = useState<string | null>(null);
  const [watchDone, setWatchDone] = useState(false);

  const procDoc = documents.find(
    (d) => d.status === "pending" || d.status === "processing"
  );
  // Prefer the just-uploaded doc; fall back to the list. Once the watched
  // doc reports done, stop deriving from the list until the refresh lands.
  const activeWatchId = watchingDocId ?? (watchDone ? null : procDoc?.id) ?? null;

  useEffect(() => {
    let evtSource: EventSource | null = null;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    const closeAll = () => {
      evtSource?.close();
      evtSource = null;
      eventSourceRef.current = null;
      if (fallbackInterval) clearInterval(fallbackInterval);
      fallbackInterval = null;
    };

    if (!activeWatchId) {
      setProcessingDoc(null);
      setProcessStage("");
      // Reset watch state once the refresh confirms the doc is done.
      setWatchingDocId(null);
      setWatchDone(false);
      return closeAll;
    }

    setProcessingDoc(activeWatchId);
    setProcessStage("processing"); // show bar immediately

    const refresh = () => {
      if (!cancelled) fetchDocuments();
    };

    const finishWatch = () => {
      setProcessStage("complete"); // show "Done!" (green)
      // Clear the watched id so activeWatchId goes null and the effect
      // tears down; watchDone blocks re-deriving from the still-pending
      // list row until the refresh lands.
      setWatchingDocId(null);
      setWatchDone(true);
      closeAll();
      refresh();
    };

    const openStream = (token: string) => {
      evtSource = new EventSource(
        `${API_BASE}/documents/${activeWatchId}/stream?token=${encodeURIComponent(token)}`
      );
      eventSourceRef.current = evtSource;

      evtSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setProcessStage(data.stage || data.status);

          if (data.stage === "complete" || data.status === "failed") {
            finishWatch();
          }
        } catch {
          // Skip malformed events
        }
      };

      evtSource.onerror = () => {
        // Stream dropped (e.g. server restart, auth expiry) — fall back to
        // polling so status still updates and stale "pending" docs refresh.
        closeAll();
        fallbackInterval = setInterval(refresh, 3000);
      };
    };

    // EventSource can't send Authorization headers — pass the token as a
    // query param (mirrors agents page). Without it the backend 401s the
    // stream and no progress is ever shown.
    supabase.auth
      .getSession()
      .then(({ data }: { data: { session: { access_token?: string } | null } }) => {
        const token = data.session?.access_token ?? "";
        if (!cancelled) openStream(token);
      })
      .catch(() => {
        if (!cancelled) openStream("");
      });

    return () => {
      cancelled = true;
      closeAll();
    };
  }, [activeWatchId, supabase, fetchDocuments]);

  const handleUpload = async (file: File) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw new Error("Not authenticated");

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const { id } = (await res.json()) as { id: string };
    // Watch this doc immediately so the progress bar shows right away —
    // waiting for the list fetch can miss fast-processing docs.
    setWatchingDocId(id);
    setWatchDone(false);
    setProcessStage("processing");
    await fetchDocuments();
  };

  const STAGE_LABELS: Record<string, string> = {
    processing: "Processing...",
    parsing: "Parsing document...",
    chunking: "Splitting into chunks...",
    embedding: "Generating embeddings...",
    extracting_entities: "Extracting entities...",
    complete: "Done!",
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Document Library" showBack backHref="/dashboard" />

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Card className="mb-8 bg-app-card border border-app-border">
          <CardHeader>
            <CardTitle className="font-display text-lg text-app-text">Upload Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <UploadDropzone onUpload={handleUpload} />
          </CardContent>
        </Card>

        {processingDoc && processStage && (
          <div className="mb-6 bg-app-card border border-app-border p-4">
            <div className="flex items-center gap-3">
              {processStage === "complete" ? (
                <>
                  <span className="inline-block w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full" />
                  <span className="text-sm font-medium text-green-600 dark:text-green-400">
                    {STAGE_LABELS[processStage] || processStage}
                  </span>
                </>
              ) : (
                <>
                  <span className="inline-block w-2 h-2 bg-amber dark:bg-amber rounded-full animate-pulse" />
                  <span className="text-sm font-medium text-app-text">
                    {STAGE_LABELS[processStage] || processStage}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 text-slate-500">Loading documents...</div>
        ) : error ? (
          <div className="text-center py-12 text-red-600 dark:text-red-400">{error}</div>
        ) : documents.length === 0 ? (
          <Card className="bg-app-card border border-app-border">
            <CardContent className="py-12 text-center">
              <p className="text-app-text font-medium mb-1">No documents yet</p>
              <p className="text-slate-500 text-sm">
                Upload your first PDF to start building the knowledge base
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-app-card border border-app-border">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-app-border hover:bg-transparent">
                    <TableHead className="text-app-muted">Filename</TableHead>
                    <TableHead className="text-app-muted">Type</TableHead>
                    <TableHead className="text-app-muted">Status</TableHead>
                    <TableHead className="text-app-muted">Pages</TableHead>
                    <TableHead className="text-app-muted">Uploaded</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.id} className="border-app-border">
                      <TableCell>
                        <Link href={`/documents/${doc.id}`} className="font-medium text-app-text text-sm hover:text-sky-600 dark:hover:text-sky-400 transition-colors">
                          {doc.filename}
                        </Link>
                        {doc.errorMessage && (
                          <p className="text-red-600 dark:text-red-400 text-xs mt-0.5 truncate max-w-xs" title={doc.errorMessage}>{doc.errorMessage.length > 80 ? doc.errorMessage.slice(0, 80) + "..." : doc.errorMessage}</p>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-app-muted font-mono">
                        {doc.fileType.split("/").pop()?.toUpperCase()}
                      </TableCell>
                      <TableCell>
                        <StatusPill status={doc.status} />
                      </TableCell>
                      <TableCell className="text-sm text-app-muted font-mono">
                        {doc.pageCount ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm text-app-muted">
                        {new Date(doc.uploadedAt).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
