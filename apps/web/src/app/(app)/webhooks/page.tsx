"use client";

import { useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import { useWebhooks } from "@/hooks/useWebhooks";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { WebhookCreateForm, WebhookSubscriptionTable, WebhookDeliveryTable } from "@/components/features/webhooks";

export default function WebhooksPage() {
  const { activeProjectId } = useProjectStore();
  const { token } = useAuth();
  const { subscriptions, deliveries, loading, error, createSubscription, toggleSubscription, deleteSubscription } = useWebhooks({ token, projectId: activeProjectId });
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async (eventType: string, url: string) => {
    setIsCreating(true);
    try {
      await createSubscription({ event_type: eventType, url });
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggle = async (id: string, active: boolean) => {
    await toggleSubscription(id, active);
  };

  const handleDelete = async (id: string) => {
    await deleteSubscription(id);
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
