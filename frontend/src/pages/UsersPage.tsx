import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus } from "lucide-react";
import { useUsers, useCreateUser, useUpdateUser } from "@/hooks/useUsers";
import { RequireRole } from "@/components/RequireRole";
import { ApiError } from "@/lib/api";
import type { Role } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Skeleton, EmptyState, ErrorState, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

const ROLE_LABEL: Record<Role, string> = { officer: "ພະນັກງານ", manager: "ຜູ້ຈັດການ", admin: "ຜູ້ດູແລ" };

export function UsersPage() {
  return (
    <RequireRole roles={["admin"]}>
      <UsersInner />
    </RequireRole>
  );
}

function UsersInner() {
  const { data: users, isLoading, error } = useUsers();
  const [showForm, setShowForm] = useState(false);

  return (
    <div>
      <PageHeader title="ຈັດການຜູ້ໃຊ້" description="ເພີ່ມ, ກຳນົດ role, ປິດການໃຊ້ງານ">
        <Button onClick={() => setShowForm((v) => !v)}>
          <UserPlus className="size-4" />
          {showForm ? "ປິດຟອມ" : "ເພີ່ມຜູ້ໃຊ້"}
        </Button>
      </PageHeader>

      {showForm && <CreateUserForm onDone={() => setShowForm(false)} />}

      <Card className={showForm ? "mt-6" : ""}>
        <CardHeader>
          <CardTitle>ຜູ້ໃຊ້ທັງໝົດ</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message="ໂຫຼດຜູ້ໃຊ້ບໍ່ສຳເລັດ" />
          ) : !users || users.length === 0 ? (
            <EmptyState title="ຍັງບໍ່ມີຜູ້ໃຊ້" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ຊື່</TableHead>
                  <TableHead>ອີເມວ</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>ສະຖານະ</TableHead>
                  <TableHead className="text-right">ຈັດການ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <UserRow key={u.uid} user={u} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function UserRow({ user }: { user: { uid: string; name: string; email: string; role: Role; is_active?: boolean } }) {
  const update = useUpdateUser();

  function changeRole(role: Role) {
    update.mutate(
      { uid: user.uid, input: { role } },
      { onSuccess: () => toast("ອັບເດດ role ແລ້ວ", { variant: "success" }) }
    );
  }
  function toggleActive() {
    update.mutate(
      { uid: user.uid, input: { is_active: !(user.is_active ?? true) } },
      { onSuccess: () => toast("ອັບເດດສະຖານະແລ້ວ", { variant: "success" }) }
    );
  }

  const active = user.is_active ?? true;
  return (
    <TableRow>
      <TableCell className="font-medium">{user.name || "-"}</TableCell>
      <TableCell className="text-sm">{user.email}</TableCell>
      <TableCell>
        <Select
          value={user.role}
          onChange={(e) => changeRole(e.target.value as Role)}
          className="h-8 w-36"
          disabled={update.isPending}
        >
          {(["officer", "manager", "admin"] as Role[]).map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}
            </option>
          ))}
        </Select>
      </TableCell>
      <TableCell>
        <Badge variant={active ? "success" : "secondary"}>{active ? "ໃຊ້ງານ" : "ປິດ"}</Badge>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="outline" size="sm" onClick={toggleActive} disabled={update.isPending}>
          {active ? "ປິດການໃຊ້ງານ" : "ເປີດໃຊ້ງານ"}
        </Button>
      </TableCell>
    </TableRow>
  );
}

const createSchema = z.object({
  name: z.string().min(1, "ກະລຸນາປ້ອນຊື່"),
  email: z.string().email("ອີເມວບໍ່ຖືກຕ້ອງ"),
  password: z.string().min(6, "ຢ່າງໜ້ອຍ 6 ຕົວ"),
  role: z.enum(["officer", "manager", "admin"]),
  department: z.string().optional(),
});
type CreateValues = z.infer<typeof createSchema>;

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const create = useCreateUser();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "officer" },
  });

  async function onSubmit(values: CreateValues) {
    try {
      await create.mutateAsync(values);
      toast("ສ້າງຜູ້ໃຊ້ສຳເລັດ", { variant: "success" });
      reset();
      onDone();
    } catch (err) {
      toast("ສ້າງຜູ້ໃຊ້ບໍ່ສຳເລັດ", {
        variant: "error",
        description: err instanceof ApiError ? String(err.detail) : undefined,
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>ເພີ່ມຜູ້ໃຊ້ໃໝ່</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>ຊື່</Label>
            <Input {...register("name")} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label>ອີເມວ</Label>
            <Input type="email" {...register("email")} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label>ລະຫັດຜ່ານເບື້ອງຕົ້ນ</Label>
            <Input type="text" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <Select {...register("role")}>
              <option value="officer">ພະນັກງານ</option>
              <option value="manager">ຜູ້ຈັດການ</option>
              <option value="admin">ຜູ້ດູແລ</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>ພະແນກ</Label>
            <Input {...register("department")} />
          </div>
          <div className="flex items-end justify-end">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Spinner />}
              ສ້າງຜູ້ໃຊ້
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
