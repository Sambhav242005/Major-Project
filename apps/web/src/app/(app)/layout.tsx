"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, token, loading: authLoading, authError } = useAuth();
  const { loadProjects, loaded: projectsLoaded } = useProject();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !authError && !user) {
      router.replace("/auth/signin");
    }
  }, [authLoading, authError, user, router]);

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

  if (authError) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-app-bg text-app-text">
      <p role="alert">{authError}</p>
      <button onClick={() => window.location.reload()} className="rounded-lg border border-app-border-strong px-4 py-2">Try again</button>
    </div>
  );

  if (!user) return null;

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <main>{children}</main>
    </div>
  );
}
