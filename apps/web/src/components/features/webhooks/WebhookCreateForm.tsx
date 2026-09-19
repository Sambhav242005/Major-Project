"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

const EVENT_TYPES = [
  "document.uploaded",
  "document.processed",
  "document.failed",
  "chat.message",
  "agent.started",
  "agent.completed",
  "agent.failed",
] as const;

interface WebhookCreateFormProps {
  onCreate: (eventType: string, url: string) => Promise<void>;
  isCreating?: boolean;
}

export function WebhookCreateForm({ onCreate, isCreating }: WebhookCreateFormProps) {
  const [eventType, setEventType] = useState<typeof EVENT_TYPES[number]>(EVENT_TYPES[0]);
  const [url, setUrl] = useState("");
  const [showForm, setShowForm] = useState(false);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    await onCreate(eventType, url.trim());
    setUrl("");
    setShowForm(false);
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
