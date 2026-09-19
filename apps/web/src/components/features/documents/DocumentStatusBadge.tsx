"use client";

import { StatusPill } from "@/components/shared/StatusPill";
import { AlertTriangle } from "lucide-react";

interface DocumentStatusBadgeProps {
  status: string;
  error_message?: string | null;
}

export function DocumentStatusBadge({ status, error_message }: DocumentStatusBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      <StatusPill status={status} />
      {status === "failed" && error_message && (
        <span className="text-[10px] text-red-400 truncate max-w-[200px]" title={error_message}>
          <AlertTriangle size={10} className="inline mr-1" />
          {error_message}
        </span>
      )}
    </div>
  );
}
