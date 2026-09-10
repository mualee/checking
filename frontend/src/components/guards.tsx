import { useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { Spinner } from "@/components/ui/misc";

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner className="size-8 text-primary" />
    </div>
  );
}

/** Blocks app pages until auth resolves; redirects to /login when unauthenticated. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { loading, authed, profile } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && (!authed || !profile)) {
      navigate({ to: "/login" });
    }
  }, [loading, authed, profile, navigate]);

  if (loading) return <FullPageSpinner />;
  if (!authed || !profile) return <FullPageSpinner />;
  return <>{children}</>;
}

/** For /login: sends already-authenticated users to the dashboard. */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { loading, authed, profile } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && authed && profile) {
      navigate({ to: "/dashboard" });
    }
  }, [loading, authed, profile, navigate]);

  if (loading) return <FullPageSpinner />;
  return <>{children}</>;
}
