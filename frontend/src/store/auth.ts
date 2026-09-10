import { create } from "zustand";
import type { UserProfile } from "@/lib/types";

interface AuthState {
  /** True once a valid local token + profile are loaded. */
  authed: boolean;
  /** Backend profile (role, name) from the local users store. */
  profile: UserProfile | null;
  /** True until the initial token check + profile fetch resolves. */
  loading: boolean;
  setAuthed: (authed: boolean) => void;
  setProfile: (profile: UserProfile | null) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  authed: false,
  profile: null,
  loading: true,
  setAuthed: (authed) => set({ authed }),
  setProfile: (profile) => set({ profile }),
  setLoading: (loading) => set({ loading }),
  reset: () => set({ authed: false, profile: null, loading: false }),
}));

/** Convenience selectors. */
export const useProfile = () => useAuthStore((s) => s.profile);
export const useRole = () => useAuthStore((s) => s.profile?.role ?? null);
