export type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "citations"; citations: { index: number; filename: string; page_number: number }[] }
  /** The generation resolved by the backend; labels this exact answer. */
  | { type: "generation"; provider: string; model: string }
  | { type: "done" };

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
        if (event.type === "error") throw new Error(event.error || "The answer could not be completed. Please try again.");
        if (event.type === "done") { completed = true; yield event; return; }
        if (event.type === "chunk" || event.type === "citations" || event.type === "generation") yield event;
      }
      if (done) break;
    }
    if (!completed) throw new Error("The response was interrupted before completion. Please try again.");
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
