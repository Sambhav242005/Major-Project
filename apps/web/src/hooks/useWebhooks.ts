/**
 * Webhook subscriptions: CRUD operations.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { WebhookSubscription, WebhookDelivery } from "@/lib/types";

interface UseWebhooksOptions {
  token: string | null;
  projectId: string | null;
}

export function useWebhooks({ token, projectId }: UseWebhooksOptions) {
  const [subscriptions, setSubscriptions] = useState<WebhookSubscription[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSubscriptions = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<WebhookSubscription[]>("/webhooks/subscriptions", {
        token,
        projectId,
      });
      setSubscriptions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  const fetchDeliveries = useCallback(async () => {
    if (!token || !projectId) return;
    try {
      const data = await apiFetch<WebhookDelivery[]>("/webhooks/deliveries?limit=20", {
        token,
        projectId,
      });
      setDeliveries(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load deliveries");
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchSubscriptions();
    fetchDeliveries();
  }, [fetchSubscriptions, fetchDeliveries]);

  const createSubscription = useCallback(
    async (payload: { event_type: string; url: string }) => {
      if (!token || !projectId) return null;
      try {
        const sub = await apiFetch<WebhookSubscription>(`/webhooks/subscriptions?event_type=${encodeURIComponent(payload.event_type)}&url=${encodeURIComponent(payload.url)}`, {
          method: "POST",
          token,
          projectId,
        });
        setSubscriptions((prev) => [...prev, sub]);
        return sub;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create webhook");
        return null;
      }
    },
    [token, projectId]
  );

  const deleteSubscription = useCallback(
    async (webhookId: string) => {
      if (!token || !projectId) return;
      try {
        await apiFetch(`/webhooks/subscriptions/${webhookId}`, {
          method: "DELETE",
          token,
          projectId,
        });
        setSubscriptions((prev) => prev.filter((s) => s.id !== webhookId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to delete webhook");
      }
    },
    [token, projectId]
  );

  const toggleSubscription = useCallback(
    async (webhookId: string, active: boolean) => {
      if (!token || !projectId) return;
      try {
        await apiFetch(`/webhooks/subscriptions/${webhookId}`, {
          method: "PATCH", token, projectId, body: { active },
        });
        setSubscriptions((prev) => prev.map((s) => s.id === webhookId ? { ...s, active } : s));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update webhook");
      }
    }, [token, projectId]
  );

  return {
    subscriptions,
    deliveries,
    loading,
    error,
    createSubscription,
    deleteSubscription,
    toggleSubscription,
    refresh: fetchSubscriptions,
  };
}
