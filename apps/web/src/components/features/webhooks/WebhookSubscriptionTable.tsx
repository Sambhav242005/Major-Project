"use client";

import { Trash2, ToggleLeft, ToggleRight, Webhook } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WebhookSubscription } from "@/lib/types";

interface WebhookSubscriptionTableProps {
  subscriptions: WebhookSubscription[];
  onToggle: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
}

export function WebhookSubscriptionTable({
  subscriptions,
  onToggle,
  onDelete,
}: WebhookSubscriptionTableProps) {
  if (subscriptions.length === 0) {
    return (
      <div className="glow-card p-8 text-center">
        <Webhook size={32} className="mx-auto mb-3 text-app-muted" />
        <p className="text-sm text-app-muted">No webhook subscriptions</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {subscriptions.map((sub) => (
        <div key={sub.id} className="glow-card p-3 flex items-center gap-3">
          <Webhook size={14} className="text-app-muted shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-mono text-app-text truncate">{sub.url}</p>
            <p className="text-[10px] text-app-muted">{sub.event_type}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => onToggle(sub.id, !sub.active)}
          >
            {sub.active ? (
              <ToggleRight size={14} className="text-emerald-400" />
            ) : (
              <ToggleLeft size={14} className="text-app-muted" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs hover:text-red-400"
            onClick={() => onDelete(sub.id)}
          >
            <Trash2 size={12} />
          </Button>
        </div>
      ))}
    </div>
  );
}
