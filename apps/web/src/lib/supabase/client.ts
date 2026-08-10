import { createBrowserClient } from "@supabase/ssr";

const MOCK_AUTH = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

// Mock user for development
const MOCK_USER = {
  id: "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  email: "mock@example.com",
};

// Mock session object
const MOCK_SESSION = {
  user: MOCK_USER,
  access_token: "mock-token-for-development",
};

export function createClient() {
  if (MOCK_AUTH) {
    // Return a mock Supabase client that always returns mock data
    return {
      auth: {
        getSession: async () => ({ data: { session: MOCK_SESSION }, error: null }),
        getUser: async () => ({ data: { user: MOCK_USER }, error: null }),
        signUp: async () => ({ data: { user: MOCK_USER }, error: null }),
        signInWithPassword: async () => ({ data: { user: MOCK_USER, session: MOCK_SESSION }, error: null }),
        signOut: async () => ({ error: null }),
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
      },
    } as any;
  }

  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
