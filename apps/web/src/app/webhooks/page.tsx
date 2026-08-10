"use client";

import { useEffect, useState } from "react";
import { DashboardHeader } from "@/components/dashboard-header";

interface WebhookSubscription {
  id: string;
  event_type: string;
  url: string;
  active: boolean;
  created_at: string;
}

interface WebhookDelivery {
  id: string;
  event_type: string;
  success: boolean;
  attempts: number;
  response_status: number | null;
  created_at: string;
}

const EVENT_TYPES = [
  "document.processed",
  "document.failed",
  "agent.completed",
  "agent.failed",
  "entity.extracted",
  "chat.completed",
];

export default function WebhooksPage() {
  const [subscriptions, setSubscriptions] = useState<WebhookSubscription[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newEvent, setNewEvent] = useState(EVENT_TYPES[0]);
  const [newUrl, setNewUrl] = useState("");
  const [newSecret, setNewSecret] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    try {
      const [subsRes, delRes] = await Promise.all([
        fetch("/api/webhooks/subscriptions"),
        fetch("/api/webhooks/deliveries?limit=20"),
      ]);
      if (subsRes.ok) setSubscriptions(await subsRes.json());
      if (delRes.ok) setDeliveries(await delRes.json());
    } catch (e) {
      console.error("Failed to fetch webhooks:", e);
    } finally {
      setLoading(false);
    }
  }

  async function createSubscription() {
    if (!newUrl) return;
    try {
      const res = await fetch(
        `/api/webhooks/subscriptions?event_type=${newEvent}&url=${encodeURIComponent(newUrl)}${newSecret ? `&secret=${encodeURIComponent(newSecret)}` : ""}`,
        { method: "POST" }
      );
      if (res.ok) {
        setShowCreate(false);
        setNewUrl("");
        setNewSecret("");
        fetchData();
      }
    } catch (e) {
      console.error("Failed to create subscription:", e);
    }
  }

  async function deleteSubscription(id: string) {
    try {
      const res = await fetch(`/api/webhooks/subscriptions/${id}`, { method: "DELETE" });
      if (res.ok) fetchData();
    } catch (e) {
      console.error("Failed to delete subscription:", e);
    }
  }

  async function testWebhook(id: string) {
    try {
      const res = await fetch(`/api/webhooks/test/${id}`, { method: "POST" });
      if (res.ok) fetchData();
    } catch (e) {
      console.error("Failed to test webhook:", e);
    }
  }

  return (
    <div className="min-h-screen bg-app-bg">
      <DashboardHeader title="Webhooks" />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-display text-lg font-semibold text-app-text">Subscriptions</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-app-card text-app-text border border-app-border-strong rounded-lg text-sm hover:bg-app-card-hover transition-colors"
          >
            Add Subscription
          </button>
        </div>

        {showCreate && (
          <div className="bg-app-card border border-app-border rounded-lg p-4 mb-6">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-app-text mb-1">Event Type</label>
                <select
                  value={newEvent}
                  onChange={(e) => setNewEvent(e.target.value)}
                  className="w-full border border-app-border-strong rounded-lg px-3 py-2 text-sm bg-app-surface-alt text-app-text placeholder:text-slate-600"
                >
                  {EVENT_TYPES.map((et) => (
                    <option key={et} value={et}>{et}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-app-text mb-1">URL</label>
                <input
                  type="url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://example.com/webhook"
                  className="w-full border border-app-border-strong rounded-lg px-3 py-2 text-sm bg-app-surface-alt text-app-text placeholder:text-slate-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-app-text mb-1">Secret (optional)</label>
                <input
                  type="text"
                  value={newSecret}
                  onChange={(e) => setNewSecret(e.target.value)}
                  placeholder="HMAC signing secret"
                  className="w-full border border-app-border-strong rounded-lg px-3 py-2 text-sm bg-app-surface-alt text-app-text placeholder:text-slate-600"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={createSubscription}
                className="px-4 py-2 bg-app-text text-app-bg rounded-lg text-sm hover:bg-app-card-hover"
              >
                Create
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 border border-app-border-strong rounded-lg text-sm text-app-muted hover:bg-app-card-hover"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-app-muted text-sm">Loading...</p>
        ) : subscriptions.length === 0 ? (
          <p className="text-app-muted text-sm">No webhook subscriptions configured.</p>
        ) : (
          <div className="bg-app-card border border-app-border rounded-lg overflow-hidden mb-8">
            <table className="w-full">
              <thead className="bg-app-surface border-b border-app-border">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Event</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">URL</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Created</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-app-muted uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border">
                {subscriptions.map((sub) => (
                  <tr key={sub.id} className="hover:bg-app-card-hover">
                    <td className="px-4 py-3 text-sm font-mono text-app-text">{sub.event_type}</td>
                    <td className="px-4 py-3 text-sm text-app-muted truncate max-w-xs">{sub.url}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        sub.active ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-500/10 text-red-600 dark:text-red-400"
                      }`}>
                        {sub.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-app-muted">
                      {sub.created_at ? new Date(sub.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => testWebhook(sub.id)}
                        className="text-xs text-amber dark:text-amber hover:underline mr-3"
                      >
                        Test
                      </button>
                      <button
                        onClick={() => deleteSubscription(sub.id)}
                        className="text-xs text-red-600 dark:text-red-400 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h2 className="font-display text-lg font-semibold text-app-text mb-4">Recent Deliveries</h2>
        {deliveries.length === 0 ? (
          <p className="text-app-muted text-sm">No deliveries yet.</p>
        ) : (
          <div className="bg-app-card border border-app-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-app-surface border-b border-app-border">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Event</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Attempts</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">HTTP Code</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-app-muted uppercase">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border">
                {deliveries.map((d) => (
                  <tr key={d.id} className="hover:bg-app-card-hover">
                    <td className="px-4 py-3 text-sm font-mono text-app-text">{d.event_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        d.success ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-500/10 text-red-600 dark:text-red-400"
                      }`}>
                        {d.success ? "Success" : "Failed"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-app-muted">{d.attempts}</td>
                    <td className="px-4 py-3 text-sm text-app-muted">{d.response_status ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-app-muted">
                      {d.created_at ? new Date(d.created_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
