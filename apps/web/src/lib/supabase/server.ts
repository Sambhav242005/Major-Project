import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { LOCAL_AUTH, LOCAL_SESSION_COOKIE } from "@/lib/auth/local";
import { validatedLocalSession } from "@/lib/auth/local-server";

const MOCK_AUTH = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

const MOCK_USER = {
  id: "mock-user-001",
  email: "mock@example.com",
};

export async function createClient() {
  if (LOCAL_AUTH) {
    const cookieStore = await cookies();
    return {
      auth: {
        getSession: async () => ({ data: { session: await validatedLocalSession(cookieStore.get(LOCAL_SESSION_COOKIE)?.value) }, error: null }),
        getUser: async () => ({ data: { user: (await validatedLocalSession(cookieStore.get(LOCAL_SESSION_COOKIE)?.value))?.user ?? null }, error: null }),
        signOut: async () => { cookieStore.delete(LOCAL_SESSION_COOKIE); return { error: null }; },
        exchangeCodeForSession: async () => ({ error: { message: "External sign-in is unavailable with local accounts." } }),
      },
    } as unknown as SupabaseClient;
  }
  if (MOCK_AUTH) {
    return {
      auth: {
        getSession: async () => ({ data: { session: { user: MOCK_USER } }, error: null }),
        getUser: async () => ({ data: { user: MOCK_USER }, error: null }),
        signOut: async () => ({ error: null }),
      },
    } as unknown as SupabaseClient;
  }

  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options as Parameters<typeof cookieStore.set>[2])
            );
          } catch {
            // setAll called from Server Component — ignore
          }
        },
      },
    }
  );
}
