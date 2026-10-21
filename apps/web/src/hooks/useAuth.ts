/**
 * Supabase authentication state hook.
 * Returns session, user, loading state, and signOut helper.
 */
"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const loadSession = async (attempt = 0) => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (cancelled) return;
        if (error) throw error;
        setUser(session?.user ?? null);
        setToken(session?.access_token ?? null);
        setAuthError(null);
        setLoading(false);
      } catch {
        if (cancelled) return;
        // A temporary API outage must not erase a valid browser session.
        if (attempt < 2) {
          retry = setTimeout(() => { void loadSession(attempt + 1); }, 3000);
        } else {
          setAuthError("The sign-in service is temporarily unavailable. Please try again.");
          setLoading(false);
        }
      }
    };
    void loadSession();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event: string, session: { user?: { id?: string; email?: string }; access_token?: string } | null) => {
        setUser(session?.user as User | null ?? null);
        setToken(session?.access_token ?? null);
      }
    );

    return () => {
      cancelled = true;
      clearTimeout(retry);
      subscription.unsubscribe();
    };
  }, []);

  const signOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    setUser(null);
    setToken(null);
  };

  return { user, token, loading, authError, signOut };
}
