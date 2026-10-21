import type { SupabaseClient } from "@supabase/supabase-js";
import type { LocalSession } from "./local";

type Listener = (event: string, session: LocalSession | null) => void;
const listeners = new Set<Listener>();

async function currentSession(): Promise<LocalSession | null> {
  const response = await fetch("/auth/local-session", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error("The sign-in service is temporarily unavailable. Please try again.");
  return (await response.json()).session ?? null;
}

export function createLocalClient(): SupabaseClient {
  return {
    auth: {
      getSession: async () => {
        try {
          return { data: { session: await currentSession() }, error: null };
        } catch {
          return { data: { session: null }, error: { message: "The sign-in service is temporarily unavailable. Please try again." } };
        }
      },
      getUser: async () => {
        try {
          return { data: { user: (await currentSession())?.user ?? null }, error: null };
        } catch {
          return { data: { user: null }, error: { message: "The sign-in service is temporarily unavailable. Please try again." } };
        }
      },
      signInWithPassword: async (credentials: { email: string; password: string }) => {
        try {
          const response = await fetch("/auth/local-login", {
            method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/json" }, body: JSON.stringify(credentials),
          });
          const result = await response.json();
          if (!response.ok) return { data: { user: null, session: null }, error: { message: result.error || "Sign-in failed." } };
          const session = await currentSession();
          if (!session) return { data: { user: null, session: null }, error: { message: "Session could not be verified. Please sign in again." } };
          listeners.forEach((listener) => listener("SIGNED_IN", session));
          return { data: { user: session.user, session }, error: null };
        } catch {
          return { data: { user: null, session: null }, error: { message: "Cannot reach the sign-in service. Please try again." } };
        }
      },
      signOut: async () => {
        try {
          const response = await fetch("/auth/local-session", { method: "DELETE", credentials: "same-origin" });
          if (!response.ok) return { error: { message: "Sign-out failed. Please try again." } };
          listeners.forEach((listener) => listener("SIGNED_OUT", null));
          return { error: null };
        } catch {
          return { error: { message: "Cannot reach the sign-in service." } };
        }
      },
      signUp: async () => ({ data: { user: null, session: null }, error: { message: "Ask the project administrator to create your account." } }),
      signInWithOAuth: async () => ({ data: null, error: { message: "External sign-in is unavailable with local accounts." } }),
      exchangeCodeForSession: async () => ({ data: null, error: { message: "External sign-in is unavailable with local accounts." } }),
      onAuthStateChange: (listener: Listener) => {
        listeners.add(listener);
        return { data: { subscription: { unsubscribe: () => listeners.delete(listener) } } };
      },
    },
  } as unknown as SupabaseClient;
}
