"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FailedDoc {
  id: string;
  filename: string;
  error_message: string | null;
  uploaded_at: string | null;
}

interface FailedDocsCardProps {
  documents: FailedDoc[];
  onRetry: (id: string) => void;
}

export function FailedDocsCard({ documents, onRetry }: FailedDocsCardProps) {
  if (documents.length === 0) return null;

  return (
    <div className="glow-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle size={16} className="text-red-400" />
        <h3 className="text-sm font-medium text-app-text">Failed Documents</h3>
      </div>
      <div className="space-y-2">
        {documents.map((doc) => (
          <div key={doc.id} className="flex items-center gap-2 text-xs">
            <span className="text-app-text truncate flex-1">{doc.filename}</span>
            <span className="text-red-400 truncate max-w-[150px]" title={doc.error_message ?? ""}>
              {doc.error_message ?? "Unknown error"}
            </span>
            <Button variant="ghost" size="sm" className="h-6 text-[10px]" onClick={() => onRetry(doc.id)}>
              Retry
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
