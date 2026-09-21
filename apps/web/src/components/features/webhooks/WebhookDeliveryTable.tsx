"use client";

import { CheckCircle, XCircle, Clock } from "lucide-react";
import type { WebhookDelivery } from "@/lib/types";

interface WebhookDeliveryTableProps {
  deliveries: WebhookDelivery[];
}

export function WebhookDeliveryTable({ deliveries }: WebhookDeliveryTableProps) {
  if (deliveries.length === 0) {
    return <p className="text-xs text-app-muted text-center py-4">No deliveries yet</p>;
  }

  return (
    <div className="space-y-2">
      {deliveries.map((d) => (
        <div key={d.id} className="glow-card p-3 flex items-center gap-3">
          {d.success ? (
            <CheckCircle size={14} className="text-emerald-400 shrink-0" />
          ) : (
            <XCircle size={14} className="text-red-400 shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-app-text">{d.event_type}</p>
            <p className="text-[10px] text-app-muted">
              Attempts: {d.attempts} {d.response_status ? `• Status: ${d.response_status}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-1 text-[10px] text-app-muted">
            <Clock size={10} />
            {d.created_at ? new Date(d.created_at).toLocaleString() : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
