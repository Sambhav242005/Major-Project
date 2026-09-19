/**
 * Document management: list, upload, track processing progress via SSE.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, withProject } from "@/lib/api/client";
import { Document, DocumentStatus } from "@/lib/validators";

interface UseDocumentsOptions {
  token: string | null;
  projectId: string | null;
}

export function useDocuments({ token, projectId }: UseDocumentsOptions) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchDocuments = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<Document[]>("/documents", { token, projectId });
      setDocuments(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Subscribe to document processing progress via SSE
  useEffect(() => {
    if (!token || !projectId) return;

    const url = withProject(`/documents/stream`, projectId);
    const es = new EventSource(`${url}?token=${encodeURIComponent(token)}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "document_status") {
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === msg.document_id
                ? { ...d, status: msg.status as DocumentStatus }
                : d
            )
          );
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [token, projectId]);

  const uploadDocument = useCallback(
    async (file: File) => {
      if (!token || !projectId) return;
      setUploading(true);
      setError(null);
      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(withProject(`/documents`, projectId), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Upload failed");
        }

        await fetchDocuments();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [token, projectId, fetchDocuments]
  );

  const deleteDocument = useCallback(
    async (documentId: string) => {
      if (!token || !projectId) return;
      try {
        await apiFetch(`/documents/${documentId}`, {
          method: "DELETE",
          token,
          projectId,
        });
        setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Delete failed");
      }
    },
    [token, projectId]
  );

  return {
    documents,
    loading,
    uploading,
    error,
    uploadDocument,
    deleteDocument,
    refresh: fetchDocuments,
  };
}
