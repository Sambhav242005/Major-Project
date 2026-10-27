import { describe, expect, it } from "vitest";
import {
  CHAT_PROVIDER_IDS,
  MAX_MODEL_LENGTH,
  buildGenerationPayload,
  chatAnswerLabel,
  chatProviderUnavailableReason,
  chatProviders,
  chatSelectionLabel,
  defaultChatProviderAvailability,
  validateChatSelection,
  type ChatModelSelection,
} from "./chat-selection";

const READY: ReturnType<typeof defaultChatProviderAvailability> = {
  serverLlmConfigured: true,
  serverChatGptConnected: true,
};

function selection(patch: Partial<ChatModelSelection> = {}): ChatModelSelection {
  return { provider: "configured", model: "", apiKey: "", ...patch };
}

describe("chat provider catalog", () => {
  it("covers the same provider set as the backend request model", () => {
    // routers/chat.py::GenerationSelection Literals
    expect([...CHAT_PROVIDER_IDS]).toEqual([
      "configured", "openai", "groq", "openrouter", "gemini", "chatgpt",
    ]);
    expect(chatProviders()).toHaveLength(CHAT_PROVIDER_IDS.length);
  });

  it("marks hosted providers as requiring an in-memory API key", () => {
    for (const meta of chatProviders()) {
      expect(meta.requiresApiKey).toBe(
        meta.id === "openai" || meta.id === "groq" || meta.id === "openrouter" || meta.id === "gemini",
      );
    }
  });
});

describe("chatProviderUnavailableReason", () => {
  it("explains a missing server default configuration", () => {
    expect(chatProviderUnavailableReason(
      "configured",
      { serverLlmConfigured: false, serverChatGptConnected: false },
    )).toMatch(/missing credentials/);
  });

  it("explains a server without a ChatGPT connection", () => {
    expect(chatProviderUnavailableReason(
      "chatgpt",
      { serverLlmConfigured: true, serverChatGptConnected: false },
    )).toMatch(/not connected on the server/);
  });

  it("keeps hosted providers selectable even when server reports problems", () => {
    const pessimistic = defaultChatProviderAvailability();
    expect(chatProviderUnavailableReason("openai", pessimistic)).toBeNull();
    expect(chatProviderUnavailableReason("groq", pessimistic)).toBeNull();
  });
});

describe("validateChatSelection", () => {
  it("accepts the server default with no model override", () => {
    expect(validateChatSelection(selection(), READY)).toBeNull();
  });

  it("accepts a server default with a printable model override", () => {
    expect(validateChatSelection(selection({ provider: "configured", model: "qwen/qwen3.8-27b" }), READY)).toBeNull();
  });

  it("requires a model ID for hosted providers", () => {
    expect(validateChatSelection(selection({ provider: "groq" }), READY)).toMatch(/model ID/);
  });

  it("requires an API key for hosted providers", () => {
    expect(validateChatSelection(selection({ provider: "groq", model: "llama-3.3-70b-versatile" }), READY))
      .toMatch(/API key/);
  });

  it("rejects API keys with interior control or non-ASCII characters like the backend", () => {
    expect(validateChatSelection(selection({ provider: "groq", model: "m", apiKey: "bad\tkey" }), READY))
      .toMatch(/printable/);
    expect(validateChatSelection(selection({ provider: "groq", model: "m", apiKey: "ключ" }), READY))
      .toMatch(/printable/);
    expect(validateChatSelection(selection({ provider: "groq", model: "m", apiKey: " gsk_rl_1 " }), READY))
      .toBeNull();
  });

  it("does not require an API key for ChatGPT server connections", () => {
    expect(validateChatSelection(selection({ provider: "chatgpt", model: "gpt-5.1" }), READY)).toBeNull();
  });

  it("blocks unavailable providers before any key check", () => {
    const pessimistic = { serverLlmConfigured: false, serverChatGptConnected: false };
    expect(validateChatSelection(selection({ provider: "chatgpt", model: "gpt-5.1" }), pessimistic))
      .toMatch(/not connected/);
    expect(validateChatSelection(selection(), pessimistic)).toMatch(/missing credentials/);
  });
});

describe("buildGenerationPayload", () => {
  it("sends only the provider when the server default stays untouched", () => {
    expect(buildGenerationPayload(selection())).toEqual({ provider: "configured" });
  });

  it("sends the trimmed model override", () => {
    expect(buildGenerationPayload(selection({ model: "  qwen/qwen3.8-27b " }))).toEqual({
      provider: "configured",
      model: "qwen/qwen3.8-27b",
    });
  });

  it("sends the API key only for hosted providers", () => {
    expect(buildGenerationPayload(selection({ provider: "groq", model: "llama-3.3-70b-versatile", apiKey: " gsk_rl_1 " })))
      .toEqual({ provider: "groq", model: "llama-3.3-70b-versatile", api_key: "gsk_rl_1" });
    expect(buildGenerationPayload(selection({ provider: "chatgpt", model: "gpt-5.1", apiKey: "leaked" })))
      .toEqual({ provider: "chatgpt", model: "gpt-5.1" });
  });
});

describe("chatSelectionLabel", () => {
  it("shows the configured default for an untouched selection", () => {
    expect(chatSelectionLabel(selection(), "ollama / qwen/qwen3.8-27b"))
      .toBe("Server default · ollama / qwen/qwen3.8-27b");
  });

  it("shows a server override distinctly", () => {
    expect(chatSelectionLabel(selection({ model: "custom/model" }), "ollama / qwen"))
      .toBe("Server · custom/model");
  });

  it("shows the provider label with the chosen model", () => {
    expect(chatSelectionLabel(selection({ provider: "groq", model: "llama-3.3-70b-versatile" }), "ollama / qwen"))
      .toBe("Groq · llama-3.3-70b-versatile");
    expect(chatSelectionLabel(selection({ provider: "gemini" }), "ollama / qwen"))
      .toBe("Google Gemini · model not set");
  });
});

describe("chatAnswerLabel", () => {
  it("labels answers with the catalog name never exposing credentials", () => {
    expect(chatAnswerLabel("groq", "llama-3.3-70b-versatile")).toBe("Groq · llama-3.3-70b-versatile");
    expect(chatAnswerLabel("configured", "qwen/qwen3.8-27b")).toBe("Server configured · qwen/qwen3.8-27b");
  });

  it("falls back to the raw resolved provider for unknown values", () => {
    expect(chatAnswerLabel("ollama", "qwen3:4b-instruct")).toBe("ollama · qwen3:4b-instruct");
  });
});

describe("MAX_MODEL_LENGTH", () => {
  it("matches the backend model field limit", () => {
    expect(MAX_MODEL_LENGTH).toBe(200);
  });
});
