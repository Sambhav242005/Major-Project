"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, token, loading: authLoading, authError } = useAuth();
  const { loadProjects, loaded: projectsLoaded, identityId, setIdentity, projects, error } = useProject();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!authLoading) setIdentity(user?.id ?? null);
  }, [authLoading, user?.id, setIdentity]);

  useEffect(() => {
    if (!authLoading && !authError && !user) {
      router.replace("/auth/signin");
    }
  }, [authLoading, authError, user, router]);

  useEffect(() => {
    if (token && user?.id === identityId && !projectsLoaded) {
      loadProjects(token);
    }
  }, [token, user?.id, identityId, projectsLoaded, loadProjects]);

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
  if (identityId !== user.id || !projectsLoaded) return <div className="p-8 text-app-muted">Loading your projects...</div>;
  if (error && !projects.length) return <div className="p-8 space-y-3"><p role="alert">{error}</p><button className="underline" onClick={() => { if (token) void loadProjects(token); }}>Retry loading projects</button></div>;
  if (!projects.length && pathname !== "/projects") return <div className="p-8 space-y-3"><p>Create a project to upload documents, chat, and use the knowledge graph.</p><Link href="/projects" className="underline">Create your first project</Link></div>;

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <main>{children}</main>
    </div>
  );
}
