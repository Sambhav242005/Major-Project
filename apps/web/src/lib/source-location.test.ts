import { describe, expect, it } from "vitest";
import { sourceLabel, transcriptCaptions, type SourceLocation } from "./source-location";

const location: SourceLocation = { kind: "transcript", start_seconds: 61.5, end_seconds: 63,
  machine_generated: true, model: "whisper" };

describe("media source locations", () => {
  it("labels transcript evidence as time ranges rather than pages", () => {
    expect(sourceLabel(location)).toBe("1:01 - 1:03 · Transcript (machine generated)");
  });
  it("builds machine captions from transcript chunks and excludes frame descriptions", () => {
    const captions = transcriptCaptions([{ text: "Launch approved", source_location: location },
      { text: "Slide description", source_location: { ...location, kind: "video_frame" } }]);
    expect(captions).toContain("00:01:01.500 --> 00:01:03.000\nLaunch approved");
    expect(captions).not.toContain("Slide description");
  });
  it("joins chunks of one transcript span into one caption cue", () => {
    const captions = transcriptCaptions([{ text: "First part", source_location: location },
      { text: "Second part", source_location: location }]);
    expect(captions.match(/ --> /g)).toHaveLength(1);
    expect(captions).toContain("First part Second part");
  });
});
