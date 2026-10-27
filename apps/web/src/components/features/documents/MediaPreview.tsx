"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { withProject } from "@/lib/api/client";
import { transcriptCaptions, type SourceLocation } from "@/lib/source-location";

interface Props {
  documentId: string;
  projectId: string | null;
  fileType: string;
  chunks: { text: string; source_location?: SourceLocation | null }[];
}

export function MediaPreview({ documentId, projectId, fileType, chunks }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [captions, setCaptions] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const player = useRef<HTMLMediaElement | null>(null);
  const [supabase] = useState(() => createClient());
  const request = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  const captionUrl = useRef<string | null>(null);

  useEffect(() => () => {
    request.current?.abort();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    if (captionUrl.current) URL.revokeObjectURL(captionUrl.current);
  }, []);

  useEffect(() => {
    const seek = () => {
      const time = Number(window.location.hash.replace(/^#t=/, ""));
      if (player.current && Number.isFinite(time) && time >= 0) player.current.currentTime = time;
    };
    window.addEventListener("hashchange", seek);
    return () => window.removeEventListener("hashchange", seek);
  }, []);

  async function load() {
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    setError(null);
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session || !projectId) throw new Error("Sign in and select a project to preview media.");
      const response = await fetch(withProject(`/documents/${documentId}/original?download=false`, projectId), {
        headers: { Authorization: `Bearer ${session.access_token}` }, signal: controller.signal,
      });
      if (!response.ok) throw new Error("Original unavailable or access denied.");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob);
      setUrl(objectUrl.current);
      if (captionUrl.current) URL.revokeObjectURL(captionUrl.current);
      captionUrl.current = URL.createObjectURL(new Blob([transcriptCaptions(chunks)], { type: "text/vtt" }));
      setCaptions(captionUrl.current);
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load media.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function seekInitialTime() {
    const time = Number(window.location.hash.replace(/^#t=/, ""));
    if (player.current && Number.isFinite(time) && time >= 0) player.current.currentTime = time;
  }

  return <section className="mb-6 rounded-lg border border-app-border p-4" aria-label="Private source media">
    {!url && <button type="button" disabled={loading} onClick={() => { void load(); }} className="text-sm underline">
      {loading ? "Loading original…" : "Load private original for playback"}
    </button>}
    {error && <p role="alert" className="text-rust text-sm">{error}</p>}
    {url && (fileType.startsWith("video/")
      ? <video ref={(element) => { player.current = element; }} src={url} controls preload="none" width={640} height={360}
          className="max-w-full" onLoadedMetadata={seekInitialTime}>
          {captions && <track src={captions} kind="captions" label="Machine transcript" default />}
        </video>
      : <audio ref={(element) => { player.current = element; }} src={url} controls preload="none" onLoadedMetadata={seekInitialTime} />)}
    <p className="mt-2 text-xs text-app-muted">Transcript and frame descriptions are machine generated. Review against the original. Select a timestamp below to seek.</p>
  </section>;
}
