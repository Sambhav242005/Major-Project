"use client";

import { useState } from "react";
import { Calendar, RefreshCw, Loader2, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface MCPSyncPanelProps {
  onSync: () => Promise<void>;
  isSyncing?: boolean;
}

export function MCPSyncPanel({ onSync, isSyncing }: MCPSyncPanelProps) {
  const [lastSync, setLastSync] = useState<string | null>(null);

  const handleSync = async () => {
    await onSync();
    setLastSync(new Date().toLocaleString());
  };

  return (
    <div className="glow-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Calendar size={16} className="text-emerald-400" />
        <h3 className="text-sm font-medium text-app-text">Google Meet Sync</h3>
      </div>
      <p className="text-xs text-app-muted mb-3">
        Sync upcoming and recent Google Meet recordings for automatic transcription
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={handleSync}
          disabled={isSyncing}
        >
          {isSyncing ? (
            <Loader2 size={12} className="mr-1 animate-spin" />
          ) : (
            <RefreshCw size={12} className="mr-1" />
          )}
          {isSyncing ? "Syncing..." : "Sync Meetings"}
        </Button>
        {lastSync && (
          <span className="flex items-center gap-1 text-[10px] text-emerald-400">
            <CheckCircle size={10} />
            Last synced: {lastSync}
          </span>
        )}
      </div>
    </div>
  );
}
