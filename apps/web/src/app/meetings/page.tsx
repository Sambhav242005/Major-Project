"use client";

import { useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { API_BASE } from "@/lib/api/client";
import { DashboardHeader } from "@/components/dashboard-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface MeetingAnalysis {
  filename?: string;
  transcript: string;
  summary: string;
  key_points: string[];
  action_items: string[];
  sentiment: string;
  sentiment_reason?: string;
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "text-emerald-600 dark:text-emerald-400",
  neutral: "text-slate-600 dark:text-slate-300",
  negative: "text-red-600 dark:text-red-400",
};

export default function MeetingsPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<MeetingAnalysis | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = async () => {
    setError(null);
    setAnalysis(null);
    try {
      // Capture the current tab (or screen) WITH audio — this is what lets
      // you record the Meet without a bot account. User picks the tab.
      const display = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      });

      let audioTrack = display.getAudioTracks()[0];
      // If no audio track (some setups), fall back to mic
      if (!audioTrack) {
        const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioTrack = mic.getAudioTracks()[0];
        display.getTracks().forEach((t) => t.stop());
      }

      // Record an AUDIO-ONLY stream: mixing a video track + audio mimeType
      // makes MediaRecorder throw NotSupportedError on some browsers.
      const audioStream = new MediaStream(
        audioTrack ? [audioTrack] : []
      );
      streamRef.current = audioStream;
      chunksRef.current = [];

      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
        .find((m) => MediaRecorder.isTypeSupported(m));

      mimeTypeRef.current = mimeType || "audio/webm";
      const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : undefined);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleStop;
      recorder.start(1000);
      recorderRef.current = recorder;
      recordingRef.current = true;
      setRecording(true);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);

      // Stop when the user ends tab sharing
      const stopOnEnd = () => {
        if (recordingRef.current) stopRecording();
      };
      display.getVideoTracks()[0]?.addEventListener("ended", stopOnEnd);
      // Keep the display video track alive so tab sharing stays active
      display.getVideoTracks().forEach((t) => {
        if (t !== display.getAudioTracks()[0]) t.enabled = false;
      });
    } catch (e) {
      setError("Could not start recording — allow tab/screen sharing with audio.");
      console.error(e);
    }
  };

  const stopRecording = () => {
    recordingRef.current = false;
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setRecording(false);
  };

  const handleStop = async () => {
    setProcessing(true);
    setError(null);
    try {
      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const ext = mimeTypeRef.current.includes("mp4") ? "m4a" : "webm";
      const formData = new FormData();
      formData.append(
        "file",
        new File([blob], `meeting.${ext}`, { type: mimeTypeRef.current })
      );

      const res = await fetch(`${API_BASE}/meetings/analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      setAnalysis((await res.json()) as MeetingAnalysis);
    } catch (e: any) {
      setError(e.message || "Failed to analyze meeting");
    } finally {
      setProcessing(false);
    }
  };

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Meetings" showBack backHref="/dashboard" />

      <main className="max-w-4xl mx-auto px-6 py-8">
        <Card className="mb-8 bg-app-card border border-app-border">
          <CardHeader>
            <CardTitle className="font-display text-lg">
              Meeting Recorder
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-app-muted mb-4">
              Start recording while you're in a Google Meet — your browser
              captures the tab's audio locally, then uploads it for
              transcription and analysis. No bot account needed.
            </p>

            <div className="mb-6 space-y-2 text-sm">
              <h3 className="text-xs text-app-muted uppercase tracking-wider mb-2">
                How it works
              </h3>
              <ol className="list-decimal pl-5 space-y-1.5 text-app-muted">
                <li>
                  Open your Google Meet in a tab (join the call first).
                </li>
                <li>
                  Click <span className="text-app-text">Start recording</span>{" "}
                  below, then in the share dialog pick the{" "}
                  <span className="text-app-text">Meet tab</span>.
                </li>
                <li>
                  Make sure{" "}
                  <span className="text-app-text">"Also share tab audio"</span>{" "}
                  is <span className="text-app-text">checked</span> in the
                  dialog — this is what captures the{" "}
                  <span className="text-app-text">
                    other participants' voices
                  </span>
                  . Without it, only your microphone is recorded.
                </li>
                <li>
                  When the meeting ends, click{" "}
                  <span className="text-app-text">Stop & analyze</span>. The
                  audio is uploaded, transcribed, and summarized.
                </li>
              </ol>

              <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs leading-relaxed">
                <span className="font-medium text-amber-500">Note:</span>{" "}
                screen sharing is required only to grant the browser access to
                the tab's audio — browsers block capturing "what you hear"
                any other way. Only the audio is recorded (no video), and it
                stays local until you click Stop. Keep the Meet tab audible
                during the call, or the recording will be silent.
              </div>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="flex items-center gap-4">
              {!recording ? (
                <Button onClick={startRecording} disabled={processing}>
                  {processing ? "Analyzing..." : "Start recording"}
                </Button>
              ) : (
                <>
                  <Button
                    onClick={stopRecording}
                    variant="destructive"
                    className="bg-rust/20 text-app-text border border-rust/40 hover:bg-rust/30"
                  >
                    Stop & analyze
                  </Button>
                  <span className="text-sm font-mono text-app-muted animate-pulse">
                    ● {formatTime(elapsed)}
                  </span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {analysis && (
          <Card className="bg-app-card border border-app-border">
            <CardHeader>
              <CardTitle className="font-display text-lg flex items-center gap-2">
                Meeting Analysis
                <span className={`text-xs font-medium ${SENTIMENT_COLORS[analysis.sentiment] || "text-app-muted"}`}>
                  {analysis.sentiment}
                  {analysis.sentiment_reason ? ` — ${analysis.sentiment_reason}` : ""}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <h3 className="text-xs text-app-muted uppercase tracking-wider mb-1.5">Summary</h3>
                <p className="text-sm leading-relaxed">{analysis.summary}</p>
              </div>

              {analysis.key_points.length > 0 && (
                <div>
                  <h3 className="text-xs text-app-muted uppercase tracking-wider mb-1.5">Key points</h3>
                  <ul className="list-disc pl-5 space-y-1 text-sm">
                    {analysis.key_points.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.action_items.length > 0 && (
                <div>
                  <h3 className="text-xs text-app-muted uppercase tracking-wider mb-1.5">Action items</h3>
                  <ul className="list-disc pl-5 space-y-1 text-sm">
                    {analysis.action_items.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.transcript && (
                <div>
                  <h3 className="text-xs text-app-muted uppercase tracking-wider mb-1.5">Transcript</h3>
                  <p className="text-sm text-app-muted whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {analysis.transcript}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
