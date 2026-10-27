import { useCallback, useState } from "react";

/**
 * Shared chat-model selection logic.
 *
 * One source of truth for the provider catalog, availability reasons,
 * validation and request payload used by the header selector and the send
 * handler in `app/(app)/chat/page.tsx` — mirrors
 * apps/api/routers/chat.py::GenerationSelection so both ends reject the same
 * selections with the same rules.
 */

export const CHAT_PROVIDER_IDS = [
  "configured",
  "openai",
  "groq",
  "openrouter",
  "gemini",
  "chatgpt",
] as const;

export type ChatProviderId = (typeof CHAT_PROVIDER_IDS)[number];

/** Mirrors the backend `model` Field max_length=200 for hosted providers. */
export const MAX_MODEL_LENGTH = 200;

export interface ChatProviderMeta {
  id: ChatProviderId;
  label: string;
  /** Hosted keys are held only in page/request memory, never stored. */
  requiresApiKey: boolean;
}

const CHAT_PROVIDERS: Record<ChatProviderId, ChatProviderMeta> = {
  configured: { id: "configured", label: "Server configured", requiresApiKey: false },
  openai: { id: "openai", label: "OpenAI API", requiresApiKey: true },
  groq: { id: "groq", label: "Groq", requiresApiKey: true },
  openrouter: { id: "openrouter", label: "OpenRouter", requiresApiKey: true },
  gemini: { id: "gemini", label: "Google Gemini", requiresApiKey: true },
  chatgpt: { id: "chatgpt", label: "ChatGPT (server connection)", requiresApiKey: false },
};

export function chatProviders(): ChatProviderMeta[] {
  return CHAT_PROVIDER_IDS.map((id) => CHAT_PROVIDERS[id]);
}

export function chatProviderMeta(provider: ChatProviderId): ChatProviderMeta {
  return CHAT_PROVIDERS[provider];
}

export interface ChatModelSelection {
  provider: ChatProviderId;
  model: string;
  apiKey: string;
}

/**
 * Availability seen from `/system/status`. The server default stays
 * optimistically true until the status endpoint proves otherwise (a failed
 * status fetch must not block working setups); ChatGPT stays disabled until
 * the server reports a connection.
 */
export interface ChatProviderAvailability {
  serverLlmConfigured: boolean;
  serverChatGptConnected: boolean;
}

export function defaultChatProviderAvailability(): ChatProviderAvailability {
  return { serverLlmConfigured: true, serverChatGptConnected: false };
}

export function chatProviderUnavailableReason(
  provider: ChatProviderId,
  availability: ChatProviderAvailability,
): string | null {
  if (provider === "configured" && !availability.serverLlmConfigured) {
    return "The server default LLM has missing credentials. Generation fails until the operator configures it.";
  }
  if (provider === "chatgpt" && !availability.serverChatGptConnected) {
    return "ChatGPT is not connected on the server. Ask the operator to connect it before selecting it.";
  }
  return null;
}

/** Mirrors the backend's printable-ASCII-only API key rule. */
function hasAcceptableApiKey(apiKey: string): boolean {
  const key = apiKey.trim();
  if (!key) return false;
  return [...key].every((char) => {
    const code = char.charCodeAt(0);
    return code >= 32 && code <= 126;
  });
}

export function validateChatSelection(
  selection: ChatModelSelection,
  availability: ChatProviderAvailability,
): string | null {
  const unavailable = chatProviderUnavailableReason(selection.provider, availability);
  if (unavailable) return unavailable;
  if (selection.provider !== "configured" && !selection.model.trim()) {
    return "Enter the model ID supplied by your provider.";
  }
  if (CHAT_PROVIDERS[selection.provider].requiresApiKey && !hasAcceptableApiKey(selection.apiKey)) {
    return "Enter an API key for this provider with standard printable characters only.";
  }
  return null;
}

export interface ChatGenerationPayload {
  provider: ChatProviderId;
  model?: string;
  api_key?: string;
}

/** Build the request-body `generation` object. Keys stay in request memory. */
export function buildGenerationPayload(selection: ChatModelSelection): ChatGenerationPayload {
  const payload: ChatGenerationPayload = { provider: selection.provider };
  const model = selection.model.trim();
  if (model) payload.model = model;
  if (CHAT_PROVIDERS[selection.provider].requiresApiKey) {
    payload.api_key = selection.apiKey.trim();
  }
  return payload;
}

/** Chip label for the selection that will apply to the next message. */
export function chatSelectionLabel(selection: ChatModelSelection, defaultModel: string): string {
  if (selection.provider === "configured") {
    const model = selection.model.trim();
    return model ? `Server · ${model}` : defaultModel ? `Server default · ${defaultModel}` : "Server default";
  }
  const meta = CHAT_PROVIDERS[selection.provider];
  const model = selection.model.trim();
  return model ? `${meta.label} · ${model}` : `${meta.label} · model not set`;
}

/** Per-answer label from the generation the backend actually resolved. */
export function chatAnswerLabel(provider: string, model: string): string {
  const meta = CHAT_PROVIDER_IDS.includes(provider as ChatProviderId)
    ? CHAT_PROVIDERS[provider as ChatProviderId]
    : null;
  return meta ? `${meta.label} · ${model}` : `${provider} · ${model}`;
}

export interface ChatSelectionController {
  selection: ChatModelSelection;
  setProvider: (provider: ChatProviderId) => void;
  setModel: (model: string) => void;
  setApiKey: (apiKey: string) => void;
  error: string | null;
  setGenerationError: (error: string | null) => void;
}

/**
 * Selection state for the current chat view. Switching provider resets the
 * model, key and any error; changes survive "New session" but reset when the
 * page unmounts (cross-navigation persistence is a separate decision).
 */
export function useChatModelSelection(): ChatSelectionController {
  const [provider, setProviderState] = useState<ChatProviderId>("configured");
  const [model, setModelState] = useState("");
  const [apiKey, setApiKeyState] = useState("");
  const [error, setError] = useState<string | null>(null);

  const setProvider = useCallback((next: ChatProviderId) => {
    setProviderState(next);
    setModelState("");
    setApiKeyState("");
    setError(null);
  }, []);

  const setModel = useCallback((next: string) => {
    setModelState(next.slice(0, MAX_MODEL_LENGTH));
    setError(null);
  }, []);

  const setApiKey = useCallback((next: string) => {
    setApiKeyState(next);
    setError(null);
  }, []);

  return {
    selection: { provider, model, apiKey },
    setProvider,
    setModel,
    setApiKey,
    error,
    setGenerationError: setError,
  };
}
