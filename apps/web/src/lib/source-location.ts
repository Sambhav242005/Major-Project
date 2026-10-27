export interface SourceLocation {
  kind: "transcript" | "video_frame";
  start_seconds: number;
  end_seconds: number;
  machine_generated: boolean;
  model: string;
}

export function sourceTime(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}

export function sourceLabel(location: SourceLocation): string {
  return `${sourceTime(location.start_seconds)}${location.end_seconds > location.start_seconds
    ? ` - ${sourceTime(location.end_seconds)}` : ""} · ${location.kind === "transcript" ? "Transcript" : "Frame description"} (machine generated)`;
}

function vttTime(seconds: number): string {
  return new Date(Math.round(seconds * 1000)).toISOString().slice(11, 23);
}

export function transcriptCaptions(chunks: { text: string; source_location?: SourceLocation | null }[]): string {
  const spans = new Map<string, { start: number; end: number; text: string[] }>();
  for (const chunk of chunks) {
    const location = chunk.source_location;
    if (location?.kind !== "transcript" || location.end_seconds <= location.start_seconds) continue;
    const key = `${location.start_seconds}:${location.end_seconds}`;
    const span = spans.get(key) ?? { start: location.start_seconds, end: location.end_seconds, text: [] };
    span.text.push(chunk.text);
    spans.set(key, span);
  }
  const cues = Array.from(spans.values()).sort((a, b) => a.start - b.start).map((span) =>
    `${vttTime(span.start)} --> ${vttTime(span.end)}\n${span.text.join(" ").replace(/-->/g, "arrow").replace(/\n\s*\n/g, "\n")}`);
  return `WEBVTT\n\n${cues.join("\n\n")}\n`;

}
