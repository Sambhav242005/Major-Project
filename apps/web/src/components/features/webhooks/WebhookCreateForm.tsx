"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

const EVENT_TYPES = [
  "document.processed",
  "document.failed",
  "chat.completed",
  "entity.extracted",
] as const;

interface WebhookCreateFormProps {
  onCreate: (eventType: string, url: string) => Promise<void>;
  isCreating?: boolean;
}

export function WebhookCreateForm({ onCreate, isCreating }: WebhookCreateFormProps) {
  const [eventType, setEventType] = useState<typeof EVENT_TYPES[number]>(EVENT_TYPES[0]);
  const [url, setUrl] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setError(null);
    try {
      const destination = new URL(url.trim());
      if (destination.protocol !== "https:") throw new Error("Use a public HTTPS endpoint.");
      await onCreate(eventType, url.trim());
      setUrl("");
      setShowForm(false);
    } catch (error) { setError(error instanceof Error ? error.message : "Could not create subscription."); }
  };

  if (!showForm) {
    return (
      <Button variant="outline" size="sm" className="text-xs" onClick={() => setShowForm(true)}>
        <Plus size={12} className="mr-1" />
        Add Subscription
      </Button>
    );
  }

  return (
    <div className="glow-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-app-text">New Subscription</h4>
        <Button variant="ghost" size="sm" className="text-xs h-6" onClick={() => setShowForm(false)}>
          Cancel
        </Button>
      </div>
      <div className="space-y-2">
        <p className="text-xs text-app-muted">Deliveries require a public HTTPS destination. Local network and private IP endpoints are blocked.</p>
        {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value as typeof EVENT_TYPES[number])}
          className="w-full bg-app-surface border border-app-border rounded-md px-3 py-1.5 text-sm text-app-text"
        >
          {EVENT_TYPES.map((et) => (
            <option key={et} value={et}>{et}</option>
          ))}
        </select>
        <input
          type="url"
          placeholder="https://your-webhook-url.com/hook"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full bg-app-surface border border-app-border rounded-md px-3 py-1.5 text-sm text-app-text placeholder:text-app-muted"
        />
        <Button
          size="sm"
          className="text-xs glow-button"
          onClick={handleSubmit}
          disabled={!url.trim() || isCreating}
        >
          {isCreating ? "Creating..." : "Create"}
        </Button>
      </div>
    </div>
  );
}
