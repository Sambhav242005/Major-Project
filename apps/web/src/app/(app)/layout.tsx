"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";
import { DashboardHeader } from "@/components/layout/dashboard-header";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, token, loading: authLoading } = useAuth();
  const { loadProjects, loaded: projectsLoaded } = useProject();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/auth/login");
    }
  }, [authLoading, user, router]);

  // Load projects once authenticated
  useEffect(() => {
    if (token && !projectsLoaded) {
      loadProjects(token);
    }
  }, [token, projectsLoaded, loadProjects]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-app-bg flex items-center justify-center">
        <div className="text-app-muted text-sm">Loading...</div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="AI Knowledge Graph Builder" />
      <main>{children}</main>
    </div>
  );
}
