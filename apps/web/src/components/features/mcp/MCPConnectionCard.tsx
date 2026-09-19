"use client";

import { useState } from "react";
import { Send, Download, Copy, Check, RefreshCw, Save, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { MCPConnectionRaw } from "@/lib/types";

interface MCPConnectionCardProps {
  connection: MCPConnectionRaw;
  onUpdate: (id: string, data: Partial<MCPConnectionRaw>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onSync: (connectionId: string) => Promise<void>;
  isSyncing?: boolean;
}

export function MCPConnectionCard({ connection, onUpdate, onDelete, onSync, isSyncing }: MCPConnectionCardProps) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(connection.name);
  const [endpointUrl, setEndpointUrl] = useState(connection.endpoint_url ?? "");
  const [authToken, setAuthToken] = useState((connection.auth_config as { token?: string })?.token ?? "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const isSender = connection.direction === "sender";
  const Icon = isSender ? Send : Download;
  const colorClass = isSender ? "text-sky-400" : "text-emerald-400";

  const handleCopy = () => {
    if (connection.endpoint_url) {
      navigator.clipboard.writeText(connection.endpoint_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(connection.id, {
        name,
        endpoint_url: endpointUrl,
        auth_config: { token: authToken },
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(connection.id);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="glow-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Icon size={16} className={colorClass} />
        <h3 className="text-sm font-medium text-app-text">{connection.name}</h3>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${isSender ? "tag-cyan" : "tag-green"}`}>
          {connection.direction}
        </span>
        <span className="text-[10px] text-app-muted ml-auto">{connection.status}</span>
      </div>

      {isSender && !editing && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={connection.endpoint_url ?? ""}
              className="flex-1 bg-app-surface border border-app-border rounded px-2 py-1 text-xs text-app-text font-mono"
            />
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleCopy}>
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={() => onSync(connection.id)}
            disabled={isSyncing}
          >
            {isSyncing ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />}
            Sync Now
          </Button>
        </div>
      )}

      {(editing || !isSender) && (
        <div className="space-y-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Connection name"
            className="w-full bg-app-surface border border-app-border rounded px-2 py-1 text-xs text-app-text"
          />
          <input
            type="url"
            value={endpointUrl}
            onChange={(e) => setEndpointUrl(e.target.value)}
            placeholder="Endpoint URL"
            className="w-full bg-app-surface border border-app-border rounded px-2 py-1 text-xs text-app-text"
          />
          <input
            type="password"
            value={authToken}
            onChange={(e) => setAuthToken(e.target.value)}
            placeholder="Auth token"
            className="w-full bg-app-surface border border-app-border rounded px-2 py-1 text-xs text-app-text"
          />
          <div className="flex gap-2">
            <Button size="sm" className="text-xs" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Save size={12} className="mr-1" />}
              Save
            </Button>
            <Button variant="ghost" size="sm" className="text-xs" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button variant="ghost" size="sm" className="text-xs hover:text-red-400 ml-auto" onClick={handleDelete} disabled={deleting}>
              <Trash2 size={12} />
            </Button>
          </div>
        </div>
      )}

      {!isSender && !editing && (
        <Button variant="outline" size="sm" className="text-xs" onClick={() => setEditing(true)}>
          Edit
        </Button>
      )}
    </div>
  );
}
