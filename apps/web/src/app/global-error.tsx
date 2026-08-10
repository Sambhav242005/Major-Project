"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          fontFamily: "Inter, sans-serif",
          backgroundColor: "#F5F3EE",
          color: "#16213E",
        }}>
          <h1 style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>Something went wrong</h1>
          <p style={{ marginBottom: "1.5rem", color: "#6B7280" }}>
            {error.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={reset}
            style={{
              padding: "0.5rem 1.5rem",
              backgroundColor: "#C9862B",
              color: "white",
              border: "none",
              borderRadius: "0.375rem",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
