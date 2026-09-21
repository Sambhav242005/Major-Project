"use client";

import { useRouter } from "next/navigation";
import { FileText, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentActions } from "./DocumentActions";
import type { Document } from "@/lib/types";

interface DocumentTableProps {
  documents: Document[];
  onRetry: (id: string) => void;
  onDelete: (id: string) => void;
  deletingIds?: Set<string>;
}

export function DocumentTable({ documents, onRetry, onDelete, deletingIds }: DocumentTableProps) {
  const router = useRouter();

  if (documents.length === 0) {
    return (
      <div className="glow-card p-8 text-center">
        <FileText size={32} className="mx-auto mb-3 text-app-muted" />
        <p className="text-sm text-app-muted">No documents uploaded yet</p>
        <p className="text-xs text-app-muted mt-1">Upload a document to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div key={doc.id} className="glow-card p-3 flex items-center gap-3">
          <FileText size={16} className="text-app-muted shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-app-text truncate">{doc.filename}</p>
            <p className="text-[10px] text-app-muted">
               {doc.fileType.toUpperCase()} • {doc.pageCount ?? "?"} pages
            </p>
          </div>
          <DocumentStatusBadge status={doc.status} error_message={doc.errorMessage} />
          <DocumentActions
            documentId={doc.id}
            status={doc.status}
            onRetry={onRetry}
            onDelete={onDelete}
            isDeleting={deletingIds?.has(doc.id)}
          />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => router.push(`/documents/${doc.id}`)}
          >
            <Eye size={12} />
          </Button>
        </div>
      ))}
    </div>
  );
}
