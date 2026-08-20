import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry auth/permission errors.
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
        if (error instanceof ApiError) return failureCount < 2;
        // Network-level failure (fetch couldn't complete at all) usually means the
        // free-tier backend is asleep and waking up — keep retrying longer for that.
        return failureCount < 6;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
