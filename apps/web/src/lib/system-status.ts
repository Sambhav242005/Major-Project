export interface SystemStatus {
  auth_mode: "mock" | "local" | "supabase";
  environment: string;
  llm: { provider: string; model: string; configured: boolean; credential_present: boolean; readiness: string; connectivity: "not_checked" };
  embedding: { provider: string; model: string; configured: boolean; connectivity: "not_checked" };
  capabilities: { document_retry: boolean; meetings_recording: boolean; meetings_history: boolean; meetings_sync: boolean; mcp_protocol: boolean; mcp_connection_management: boolean; webhooks: boolean; chatgpt: boolean };
}
