import { useEffect, type ReactNode } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { UserProfile } from "@/lib/types";

/**
 * Bridges Firebase auth state into the Zustand store and fetches the backend
 * profile (role) from GET /users/me. Renders children once resolved.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const setFirebaseUser = useAuthStore((s) => s.setFirebaseUser);
  const setProfile = useAuthStore((s) => s.setProfile);
  const setLoading = useAuthStore((s) => s.setLoading);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (user) => {
      setFirebaseUser(user);
      if (!user) {
        setProfile(null);
        setLoading(false);
        return;
      }
      try {
        const profile = await api.get<UserProfile>("/users/me");
        setProfile(profile);
      } catch (err) {
        // If the profile can't be loaded (e.g. unprovisioned user), sign out.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setProfile(null);
        } else {
          setProfile(null);
        }
      } finally {
        setLoading(false);
      }
    });
    return unsub;
  }, [setFirebaseUser, setProfile, setLoading]);

  return <>{children}</>;
}
