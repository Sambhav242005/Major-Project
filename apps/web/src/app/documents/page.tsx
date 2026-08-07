"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { UploadDropzone } from "@/components/UploadDropzone";
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
  const supabase = createClient();

  const fetchDocuments = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/documents", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (res.ok) {
        const data = await res.json();
        const parsed = DocumentListSchema.safeParse(data);
        if (parsed.success) {
          setDocuments(parsed.data.documents);
        } else {
          console.error("Invalid response:", parsed.error);
          setDocuments(data.documents || []);
        }
      }
    } catch (e) {
      console.error("Failed to fetch documents:", e);
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const hasProcessing = documents.some(
    (d) => d.status === "pending" || d.status === "processing"
  );

  useEffect(() => {
    if (!hasProcessing) return;
    const interval = setInterval(fetchDocuments, 3000);
    return () => clearInterval(interval);
  }, [hasProcessing, fetchDocuments]);

  const handleUpload = async (file: File) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw new Error("Not authenticated");

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://localhost:8000/documents", {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    await fetchDocuments();
  };

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-slate hover:text-ink transition-colors">
              ← Dashboard
            </Link>
            <h1 className="font-display text-xl font-semibold text-ink">
              Document Library
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/chat" className="text-sm text-slate hover:text-ink transition-colors">
              Chat
            </Link>
            <Link href="/graph" className="text-sm text-slate hover:text-ink transition-colors">
              Graph
            </Link>
            <Link href="/agents" className="text-sm text-slate hover:text-ink transition-colors">
              Agents
            </Link>
            <Link href="/mcp" className="text-sm text-slate hover:text-ink transition-colors">
              MCP
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
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="font-display text-lg">Upload Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <UploadDropzone onUpload={handleUpload} />
          </CardContent>
        </Card>

        {loading ? (
          <div className="text-center py-12 text-slate">Loading documents...</div>
        ) : error ? (
          <div className="text-center py-12 text-rust">{error}</div>
        ) : documents.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-ink font-medium mb-1">No documents yet</p>
              <p className="text-slate text-sm">
                Upload your first PDF to start building the knowledge base
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Filename</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Pages</TableHead>
                    <TableHead>Uploaded</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell>
                        <Link href={`/documents/${doc.id}`} className="font-medium text-ink text-sm hover:text-amber transition-colors">
                          {doc.filename}
                        </Link>
                        {doc.errorMessage && (
                          <p className="text-rust text-xs mt-0.5">{doc.errorMessage}</p>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-slate font-mono">
                        {doc.fileType.split("/").pop()?.toUpperCase()}
                      </TableCell>
                      <TableCell>
                        <StatusPill status={doc.status} />
                      </TableCell>
                      <TableCell className="text-sm text-slate font-mono">
                        {doc.pageCount ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm text-slate">
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
