import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Role, UserProfile } from "@/lib/types";

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserProfile[]>("/users"),
  });
}

export interface CreateUserInput {
  name: string;
  email: string;
  password: string;
  role: Role;
  department?: string;
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateUserInput) => api.post<UserProfile>("/users", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export interface UpdateUserInput {
  role?: Role;
  is_active?: boolean;
  name?: string;
  department?: string;
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ uid, input }: { uid: string; input: UpdateUserInput }) =>
      api.patch<UserProfile>(`/users/${uid}`, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}
