import { useEffect, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { getToken, clearToken } from "@/lib/authClient";
import { useAuthStore } from "@/store/auth";
import type { UserProfile } from "@/lib/types";

/**
 * On mount, if a local auth token is present, load the backend profile (role)
 * from GET /users/me and mark the session authenticated. Renders children once
 * resolved. Re-checks whenever another part of the app changes `authed`
 * (e.g. after login/logout), so the profile stays in sync.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const authed = useAuthStore((s) => s.authed);
  const setAuthed = useAuthStore((s) => s.setAuthed);
  const setProfile = useAuthStore((s) => s.setProfile);
  const setLoading = useAuthStore((s) => s.setLoading);

  useEffect(() => {
    let cancelled = false;

    async function resolveSession() {
      if (!getToken()) {
        if (cancelled) return;
        setProfile(null);
        setAuthed(false);
        setLoading(false);
        return;
      }
      try {
        const profile = await api.get<UserProfile>("/users/me");
        if (cancelled) return;
        setProfile(profile);
        setAuthed(true);
      } catch (err) {
        if (cancelled) return;
        // Invalid/expired token or unprovisioned user: drop the session.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          clearToken();
        }
        setProfile(null);
        setAuthed(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void resolveSession();
    return () => {
      cancelled = true;
    };
    // Re-run when `authed` is toggled by login/logout.
  }, [authed, setAuthed, setProfile, setLoading]);

  return <>{children}</>;
}
