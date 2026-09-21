"use client";

import { Clock } from "lucide-react";

interface Activity {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string | null;
}

interface RecentActivityCardProps {
  activities: Activity[];
}

export function RecentActivityCard({ activities }: RecentActivityCardProps) {
  if (activities.length === 0) {
    return (
      <div className="glow-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Clock size={16} className="text-sky-400" />
          <h3 className="text-sm font-medium text-app-text">Recent Activity</h3>
        </div>
        <p className="text-xs text-app-muted">No recent activity</p>
      </div>
    );
  }

  return (
    <div className="glow-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} className="text-sky-400" />
        <h3 className="text-sm font-medium text-app-text">Recent Activity</h3>
      </div>
      <div className="space-y-2">
        {activities.map((a) => (
          <div key={a.id} className="flex items-center gap-2 text-xs">
            <span className="text-app-muted shrink-0">
              {a.created_at ? new Date(a.created_at).toLocaleDateString() : "—"}
            </span>
            <span className="text-app-text">
              {a.action} {a.resource_type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
