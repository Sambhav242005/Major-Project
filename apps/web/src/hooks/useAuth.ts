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

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getSession().then(({ data: { session } }: { data: { session: import("@supabase/supabase-js").Session | null } }) => {
      setUser(session?.user ?? null);
      setToken(session?.access_token ?? null);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event: string, session: { user?: { id?: string; email?: string }; access_token?: string } | null) => {
        setUser(session?.user as User | null ?? null);
        setToken(session?.access_token ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    setUser(null);
    setToken(null);
  };

  return { user, token, loading, signOut };
}
