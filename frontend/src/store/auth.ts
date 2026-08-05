import { create } from "zustand";
import type { User as FirebaseUser } from "firebase/auth";
import type { UserProfile } from "@/lib/types";

interface AuthState {
  /** Firebase auth user (identity). */
  firebaseUser: FirebaseUser | null;
  /** Backend profile (role, name) from Firestore users/{uid}. */
  profile: UserProfile | null;
  /** True until the initial Firebase auth state + profile fetch resolves. */
  loading: boolean;
  setFirebaseUser: (user: FirebaseUser | null) => void;
  setProfile: (profile: UserProfile | null) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  firebaseUser: null,
  profile: null,
  loading: true,
  setFirebaseUser: (firebaseUser) => set({ firebaseUser }),
  setProfile: (profile) => set({ profile }),
  setLoading: (loading) => set({ loading }),
  reset: () => set({ firebaseUser: null, profile: null, loading: false }),
}));

/** Convenience selectors. */
export const useProfile = () => useAuthStore((s) => s.profile);
export const useRole = () => useAuthStore((s) => s.profile?.role ?? null);
