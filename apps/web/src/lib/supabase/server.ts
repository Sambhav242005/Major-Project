import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

const MOCK_AUTH = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

const MOCK_USER = {
  id: "mock-user-001",
  email: "mock@example.com",
};

export async function createClient() {
  if (MOCK_AUTH) {
    return {
      auth: {
        getSession: async () => ({ data: { session: { user: MOCK_USER } }, error: null }),
        getUser: async () => ({ data: { user: MOCK_USER }, error: null }),
        signOut: async () => ({ error: null }),
      },
    } as any;
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
