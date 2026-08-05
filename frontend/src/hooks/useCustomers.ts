import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

export function useCustomers() {
  return useQuery({
    queryKey: ["customers"],
    queryFn: () => api.get<Customer[]>("/customers"),
  });
}

export function useCustomer(id: string) {
  return useQuery({
    queryKey: ["customers", id],
    queryFn: () => api.get<Customer>(`/customers/${id}`),
    enabled: !!id,
  });
}

export interface CustomerInput {
  full_name: string;
  national_id?: string;
  phone?: string;
  address?: string;
  account_no?: string;
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CustomerInput) => api.post<Customer>("/customers", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useUpdateCustomer(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<CustomerInput> & { status?: string }) =>
      api.put<Customer>(`/customers/${id}`, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["customers", id] });
    },
  });
}
