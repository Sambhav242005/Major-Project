"use client";

import { useEffect } from "react";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Root layout error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-app-bg text-app-text">
      <h1 className="text-xl font-semibold mb-4">Something went wrong</h1>
      <p className="text-app-muted mb-6">
        {error.message || "An unexpected error occurred"}
      </p>
      <button
        onClick={reset}
        className="px-6 py-2 bg-amber dark:text-app-bg rounded-lg hover:bg-amber/90 transition-colors text-sm"
      >
        Try again
      </button>
    </div>
  );
}
