"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { MeetingAnalysis } from "@/lib/types";

export function useMeetings({ token, projectId }: { token: string | null; projectId: string | null }) {
  const [analysis, setAnalysis] = useState<MeetingAnalysis | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<MeetingAnalysis[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    if (!token || !projectId) { setHistory([]); return; }
    setHistoryLoading(true);
    try {
      const result = await apiFetch<{ meetings: MeetingAnalysis[] }>("/meetings", { token, projectId });
      setHistory(result.meetings ?? []);
      setHistoryError(null);
    } catch (error) { setHistoryError(error instanceof Error ? error.message : "Could not load meeting history"); }
    finally { setHistoryLoading(false); }
  }, [token, projectId]);

  useEffect(() => {
    setAnalysis(null);
    setHistory([]);
    setError(null);
    void refreshHistory();
  }, [refreshHistory]);

  const analyzeMeeting = useCallback(async (file: File) => {
    if (!token || !projectId) throw new Error("Not authenticated");
    setProcessing(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await apiFetch<MeetingAnalysis>("/meetings/analyze", { method: "POST", token, projectId, body, timeoutMs: 300000 });
      setAnalysis(result);
      await refreshHistory();
      return result;
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to analyze meeting";
      setError(message);
      throw e;
    } finally { setProcessing(false); }
  }, [token, projectId, refreshHistory]);

  return { analysis, processing, error, analyzeMeeting, history, historyLoading, historyError, refreshHistory, selectAnalysis: setAnalysis };
}
