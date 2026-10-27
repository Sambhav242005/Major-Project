export type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "citations"; citations: { index: number; filename: string; page_number: number }[] }
  | { type: "done"; request_id?: string }
  | { type: "error"; error: string; request_id?: string };

/** Stream error that may carry the outbound model request id. */
export class ChatStreamError extends Error {
  requestId?: string;

  constructor(message: string, requestId?: string) {
    super(message);
    this.name = "ChatStreamError";
    this.requestId = requestId;
  }
}

/** Require the server's terminal success marker; EOF alone is not success. */
export async function* readChatStream(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      if (done && buffer) { lines.push(buffer); buffer = ""; }
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const event = JSON.parse(line.slice(5).trim());
        if (event.type === "error") throw new ChatStreamError(event.error || "The answer could not be completed. Please try again.", event.request_id);
        if (event.type === "done") { completed = true; yield event; return; }
        if (event.type === "chunk" || event.type === "citations") yield event;
      }
      if (done) break;
    }
    if (!completed) throw new ChatStreamError("The response was interrupted before completion. Please try again.");
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
