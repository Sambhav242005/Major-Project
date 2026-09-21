"use client";

import { RotateCcw, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DocumentActionsProps {
  documentId: string;
  status: string;
  onRetry: (id: string) => void;
  onDelete: (id: string) => void;
  isDeleting?: boolean;
}

export function DocumentActions({ documentId, status, onRetry, onDelete, isDeleting }: DocumentActionsProps) {
  return (
    <div className="flex items-center gap-1">
      {status === "failed" && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => onRetry(documentId)}
        >
          <RotateCcw size={12} />
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 text-xs hover:text-red-400"
        onClick={() => onDelete(documentId)}
        disabled={isDeleting}
      >
        {isDeleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </Button>
    </div>
  );
}
