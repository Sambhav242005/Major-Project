import { describe, expect, it } from "vitest";
import {
  ALLOWED_FILE_TYPES,
  DocumentUploadSchema,
  IMAGE_MAX_FILE_SIZE,
  MAX_FILE_SIZE,
  NOT_YET_SUPPORTED_MESSAGE,
  sizeLimitMessage,
} from "@/lib/validators";

describe("DocumentUploadSchema", () => {
  it("accepts every mirrored knowledge-source format", () => {
    for (const fileType of ALLOWED_FILE_TYPES) {
      const parsed = DocumentUploadSchema.safeParse({ filename: "source.bin", fileType, size: 1024 });
      expect(parsed.success).toBe(true);
    }
  });

  it("accepts supported audio for server-side runtime validation", () => {
    const parsed = DocumentUploadSchema.safeParse({ filename: "voice.mp3", fileType: "audio/mpeg", size: 1024 });
    expect(parsed.success).toBe(true);
  });

  it("enforces the 15MB image cap and the 25MB document cap separately", () => {
    const oversizedImage = DocumentUploadSchema.safeParse({
      filename: "scan.png",
      fileType: "image/png",
      size: IMAGE_MAX_FILE_SIZE + 1,
    });
    expect(oversizedImage.success).toBe(false);
    if (!oversizedImage.success) {
      expect(oversizedImage.error.issues[0].message).toContain("15MB limit for images");
    }

    const stillValidDocument = DocumentUploadSchema.safeParse({
      filename: "report.pdf",
      fileType: "application/pdf",
      size: IMAGE_MAX_FILE_SIZE + 1,
    });
    expect(stillValidDocument.success).toBe(true); // 15MB+1 is still a valid document

    const oversizedDocument = DocumentUploadSchema.safeParse({
      filename: "report.pdf",
      fileType: "application/pdf",
      size: MAX_FILE_SIZE + 1,
    });
    expect(oversizedDocument.success).toBe(false);
    if (!oversizedDocument.success) {
      expect(oversizedDocument.error.issues[0].message).toContain("25MB limit for documents");
    }
  });

  it("rejects empty files before any upload request is made", () => {
    const parsed = DocumentUploadSchema.safeParse({ filename: "empty.txt", fileType: "text/plain", size: 0 });
    expect(parsed.success).toBe(false);
  });
});

describe("sizeLimitMessage", () => {
  it("names the category and the file", () => {
    expect(sizeLimitMessage("image/jpeg", "scan.jpg")).toBe("scan.jpg: the file exceeds the 15MB limit for images");
    expect(sizeLimitMessage("text/plain")).toBe("the file exceeds the 25MB limit for documents");
  });
});

describe("future media categories", () => {
  it("explains that media requires configured runtimes", () => {
    expect(NOT_YET_SUPPORTED_MESSAGE).toContain("Whisper");
  });
});
