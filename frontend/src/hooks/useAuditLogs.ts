import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuditAction, AuditLog } from "@/lib/types";

export interface AuditFilters {
  user_id?: string;
  action?: AuditAction | "";
  start?: string;
  end?: string;
}

export function useAuditLogs(filters: AuditFilters) {
  const params = new URLSearchParams();
  if (filters.user_id) params.set("user_id", filters.user_id);
  if (filters.action) params.set("action", filters.action);
  if (filters.start) params.set("start", filters.start);
  if (filters.end) params.set("end", filters.end);
  const qs = params.toString();

  return useQuery({
    queryKey: ["audit-logs", filters],
    queryFn: () => api.get<AuditLog[]>(`/audit-logs${qs ? `?${qs}` : ""}`),
  });
}
