"use client";

import { Badge } from "@/components/ui/badge";

const statusConfig = {
  pending: { label: "Pending", variant: "secondary" as const },
  processing: { label: "Processing", variant: "outline" as const },
  processed: { label: "Processed", variant: "default" as const },
  failed: { label: "Failed", variant: "destructive" as const },
} as const;

type Status = keyof typeof statusConfig;

export function StatusPill({ status }: { status: string }) {
  const config = statusConfig[status as Status] || statusConfig.pending;

  return (
    <Badge variant={config.variant}>
      <span
        className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
          status === "processing" ? "animate-pulse bg-amber" :
          status === "processed" ? "bg-verified" :
          status === "failed" ? "bg-rust" : "bg-slate"
        }`}
      />
      {config.label}
    </Badge>
  );
}
