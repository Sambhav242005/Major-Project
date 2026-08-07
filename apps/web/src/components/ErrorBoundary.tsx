"use client";

import { useEffect, useState } from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function ErrorBoundary({ children, fallback }: ErrorBoundaryProps) {
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const handler = (event: ErrorEvent) => {
      setError(new Error(event.message));
      event.preventDefault();
    };
    window.addEventListener("error", handler);
    return () => window.removeEventListener("error", handler);
  }, []);

  if (error) {
    return (
      fallback || (
        <div className="min-h-screen bg-paper flex items-center justify-center">
          <div className="text-center">
            <h2 className="font-display text-xl font-semibold text-ink mb-2">
              Something went wrong
            </h2>
            <p className="text-slate text-sm mb-4">{error.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="text-sm text-amber hover:underline"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    );
  }

  return <>{children}</>;
}

export function LoadingSpinner({ text = "Loading..." }: { text?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 border-2 border-slate/20 border-t-amber rounded-full animate-spin" />
        <span className="text-sm text-slate">{text}</span>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="text-center py-12">
      <p className="text-ink font-medium mb-1">{title}</p>
      <p className="text-slate text-sm mb-4">{description}</p>
      {action}
    </div>
  );
}
