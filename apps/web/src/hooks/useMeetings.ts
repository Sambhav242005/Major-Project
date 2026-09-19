"use client";

import { useCallback, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { MeetingAnalysis } from "@/lib/types";

export function useMeetings({ token, projectId }: { token: string | null; projectId: string | null }) {
  const [analysis, setAnalysis] = useState<MeetingAnalysis | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzeMeeting = useCallback(async (file: File) => {
    if (!token || !projectId) throw new Error("Not authenticated");
    setProcessing(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await apiFetch<MeetingAnalysis>("/meetings/analyze", { method: "POST", token, projectId, body });
      setAnalysis(result);
      return result;
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to analyze meeting";
      setError(message);
      throw e;
    } finally { setProcessing(false); }
  }, [token, projectId]);

  return { analysis, processing, error, analyzeMeeting };
}
