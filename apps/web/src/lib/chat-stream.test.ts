import { describe, expect, it } from "vitest";
import { readChatStream } from "./chat-stream";

function stream(...parts: string[]) {
  return new ReadableStream<Uint8Array>({ start(controller) {
    for (const part of parts) controller.enqueue(new TextEncoder().encode(part));
    controller.close();
  } });
}

describe("chat stream terminal handling", () => {
  it("handles split SSE frames and a final completion without a newline", async () => {
    const events = [];
    for await (const event of readChatStream(stream('data: {"type":"chunk","con', 'tent":"Hello"}\n\ndata: {"type":"done"}'))) events.push(event);
    expect(events).toEqual([{ type: "chunk", content: "Hello" }, { type: "done" }]);
  });
  it("passes the model request id on completion", async () => {
    const events = [];
    for await (const event of readChatStream(stream('data: {"type":"done","request_id":"req-1"}'))) events.push(event);
    expect(events).toEqual([{ type: "done", request_id: "req-1" }]);
  });
  it("attaches the model request id to server errors", async () => {
    const consume = async () => { for await (const event of readChatStream(stream('data: {"type":"chunk","content":"partial"}\n', 'data: {"type":"error","error":"Authorization required","request_id":"req-2"}\n'))) void event; };
    const failure = await consume().catch((error: unknown) => error);
    expect(failure).toMatchObject({ name: "ChatStreamError", message: "Authorization required", requestId: "req-2" });
  });
  it("rejects server errors after partial output without a request id", async () => {
    const consume = async () => { for await (const event of readChatStream(stream('data: {"type":"chunk","content":"partial"}\n', 'data: {"type":"error","error":"Authorization required"}\n'))) void event; };
    const failure = await consume().catch((error: unknown) => error);
    expect(failure).toMatchObject({ name: "ChatStreamError", message: "Authorization required", requestId: undefined });
  });
  it("rejects transport EOF without a success event", async () => {
    const consume = async () => { for await (const event of readChatStream(stream('data: {"type":"chunk","content":"partial"}\n'))) void event; };
    await expect(consume()).rejects.toThrow("interrupted");
  });
});
