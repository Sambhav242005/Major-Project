"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { WebhookCreateForm, WebhookSubscriptionTable, WebhookDeliveryTable } from "@/components/features/webhooks";
import type { WebhookSubscription, WebhookDelivery } from "@/lib/types";

export default function WebhooksPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const { activeProjectId } = useProjectStore();
  const [subscriptions, setSubscriptions] = useState<WebhookSubscription[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const getToken = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  };

  const fetchData = async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const [subs, dels] = await Promise.all([
        apiFetch<WebhookSubscription[]>("/webhooks/subscriptions", { token, projectId: activeProjectId }),
        apiFetch<WebhookDelivery[]>("/webhooks/deliveries?limit=20", { token, projectId: activeProjectId }),
      ]);
      setSubscriptions(subs || []);
      setDeliveries(dels || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [activeProjectId]);

  const handleCreate = async (eventType: string, url: string) => {
    setIsCreating(true);
    try {
      const token = await getToken();
      if (!token) return;
      await apiFetch(`/webhooks/subscriptions?event_type=${encodeURIComponent(eventType)}&url=${encodeURIComponent(url)}`, {
        method: "POST", token, projectId: activeProjectId,
      });
      await fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create subscription");
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggle = async (id: string, active: boolean) => {
    const token = await getToken();
    if (!token) return;
    await apiFetch(`/webhooks/subscriptions/${id}`, {
      method: "PATCH", token, projectId: activeProjectId,
      body: { active },
    });
    fetchData();
  };

  const handleDelete = async (id: string) => {
    const token = await getToken();
    if (!token) return;
    await apiFetch(`/webhooks/subscriptions/${id}`, {
      method: "DELETE", token, projectId: activeProjectId,
    });
    fetchData();
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Webhooks" />
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h2 className="font-display text-lg font-semibold text-app-text mb-3">Subscriptions</h2>
          <WebhookCreateForm onCreate={handleCreate} isCreating={isCreating} />
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-app-muted text-sm">Loading...</p>
        ) : (
          <WebhookSubscriptionTable subscriptions={subscriptions} onToggle={handleToggle} onDelete={handleDelete} />
        )}

        <div>
          <h2 className="font-display text-lg font-semibold text-app-text mb-3">Recent Deliveries</h2>
          <WebhookDeliveryTable deliveries={deliveries} />
        </div>
      </main>
    </div>
  );
}
