import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Approval, Statement, Transaction } from "@/lib/types";

/** Upload source: bank × medium. */
export type UploadSource = "auto" | "digital" | "scan" | "jbl" | "jbl_scan";

export function useStatements(customerId: string) {
  return useQuery({
    queryKey: ["customers", customerId, "statements"],
    queryFn: () => api.get<Statement[]>(`/customers/${customerId}/statements`),
    enabled: !!customerId,
  });
}

export function useStatement(customerId: string, statementId: string) {
  return useQuery({
    queryKey: ["customers", customerId, "statements", statementId],
    queryFn: () => api.get<Statement>(`/customers/${customerId}/statements/${statementId}`),
    enabled: !!customerId && !!statementId,
    refetchInterval: (query) => {
      const s = query.state.data as Statement | undefined;
      // Poll while the pipeline is still running.
      return s && (s.processing_status === "processing" || s.processing_status === "pending")
        ? 1500
        : false;
    },
  });
}

export function useTransactions(customerId: string, statementId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["customers", customerId, "statements", statementId, "transactions"],
    queryFn: () =>
      api.get<Transaction[]>(`/customers/${customerId}/statements/${statementId}/transactions`),
    enabled: enabled && !!customerId && !!statementId,
  });
}

export function useUploadStatement(customerId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      openingBalance,
      source,
    }: {
      file: File;
      openingBalance?: string;
      source?: UploadSource;
    }) => {
      const fd = new FormData();
      fd.append("file", file);
      if (openingBalance) fd.append("opening_balance", openingBalance);
      if (source) fd.append("source", source);
      return api.upload<Statement>(`/customers/${customerId}/statements`, fd);
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["customers", customerId, "statements"] }),
  });
}

export function useRevalidateStatement(customerId: string, statementId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transactions: Transaction[]) =>
      api.post<Statement>(
        `/customers/${customerId}/statements/${statementId}/revalidate`,
        { transactions },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers", customerId, "statements", statementId] });
      qc.invalidateQueries({
        queryKey: ["customers", customerId, "statements", statementId, "transactions"],
      });
    },
  });
}

export interface ApprovalInput {
  decision: "approved" | "rejected" | "partial";
  approved_amount: number;
  reason: string;
}

export function useApprovals(customerId: string, statementId: string) {
  return useQuery({
    queryKey: ["customers", customerId, "statements", statementId, "approvals"],
    queryFn: () =>
      api.get<Approval[]>(`/customers/${customerId}/statements/${statementId}/approvals`),
    enabled: !!customerId && !!statementId,
  });
}

export function useApproveStatement(customerId: string, statementId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ApprovalInput) =>
      api.post<Approval>(`/customers/${customerId}/statements/${statementId}/approve`, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers", customerId, "statements", statementId] });
      qc.invalidateQueries({
        queryKey: ["customers", customerId, "statements", statementId, "approvals"],
      });
    },
  });
}

export function useDownloadReport(customerId: string, statementId: string) {
  return useMutation({
    mutationFn: async (format: "pdf" | "docx" = "pdf") => {
      const { blob, filename } = await api.getBlob(
        `/customers/${customerId}/statements/${statementId}/report/file?format=${format}`
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "report.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });
}
