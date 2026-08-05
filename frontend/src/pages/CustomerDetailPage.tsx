import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { ArrowLeft, FileUp, Pencil } from "lucide-react";
import { useCustomer, useUpdateCustomer } from "@/hooks/useCustomers";
import { useStatements } from "@/hooks/useStatements";
import { ApiError } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader, Skeleton, EmptyState, ErrorState } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

export function CustomerDetailPage({ customerId }: { customerId: string }) {
  const { data: customer, isLoading, error } = useCustomer(customerId);
  const [editing, setEditing] = useState(false);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error)
    return (
      <ErrorState
        message={error instanceof ApiError ? String(error.detail) : "ໂຫຼດຂໍ້ມູນລູກຄ້າບໍ່ສຳເລັດ"}
      />
    );
  if (!customer) return <EmptyState title="ບໍ່ພົບລູກຄ້າ" />;

  return (
    <div>
      <Link to="/customers" className={buttonVariants({ variant: "ghost", size: "sm" }) + " mb-4"}>
        <ArrowLeft className="size-4" />
        ກັບຄືນ
      </Link>
      <PageHeader title={customer.full_name} description={`ເລກບັນຊີ: ${customer.account_no || "-"}`}>
        <Link
          to="/customers/$customerId/statements/new"
          params={{ customerId }}
          className={buttonVariants()}
        >
          <FileUp className="size-4" />
          ອັບໂຫລດ Statement
        </Link>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>ຂໍ້ມູນລູກຄ້າ</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => setEditing((v) => !v)}>
              <Pencil className="size-4" />
              {editing ? "ຍົກເລີກ" : "ແກ້ໄຂ"}
            </Button>
          </CardHeader>
          <CardContent>
            {editing ? (
              <EditForm customerId={customerId} customer={customer} onDone={() => setEditing(false)} />
            ) : (
              <dl className="space-y-3 text-sm">
                <Row label="ເລກບັດປະຈຳຕົວ" value={customer.national_id} />
                <Row label="ເບີໂທ" value={customer.phone} />
                <Row label="ທີ່ຢູ່" value={customer.address} />
                <Row label="ສ້າງເມື່ອ" value={formatDate(customer.created_at)} />
              </dl>
            )}
          </CardContent>
        </Card>

        <div className="lg:col-span-2">
          <StatementsList customerId={customerId} />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between border-b pb-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value || "-"}</dd>
    </div>
  );
}

function EditForm({
  customerId,
  customer,
  onDone,
}: {
  customerId: string;
  customer: { full_name: string; national_id?: string; phone?: string; address?: string; account_no?: string };
  onDone: () => void;
}) {
  const update = useUpdateCustomer(customerId);
  const { register, handleSubmit } = useForm({ defaultValues: customer });

  async function onSubmit(values: typeof customer) {
    try {
      await update.mutateAsync(values);
      toast("ບັນທຶກສຳເລັດ", { variant: "success" });
      onDone();
    } catch (err) {
      toast("ບັນທຶກບໍ່ສຳເລັດ", {
        variant: "error",
        description: err instanceof ApiError ? String(err.detail) : undefined,
      });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <div className="space-y-1.5">
        <Label>ຊື່</Label>
        <Input {...register("full_name")} />
      </div>
      <div className="space-y-1.5">
        <Label>ເລກບັນຊີ</Label>
        <Input {...register("account_no")} />
      </div>
      <div className="space-y-1.5">
        <Label>ເບີໂທ</Label>
        <Input {...register("phone")} />
      </div>
      <div className="space-y-1.5">
        <Label>ທີ່ຢູ່</Label>
        <Input {...register("address")} />
      </div>
      <Button type="submit" size="sm" disabled={update.isPending} className="w-full">
        ບັນທຶກ
      </Button>
    </form>
  );
}

function StatementsList({ customerId }: { customerId: string }) {
  const { data: statements, isLoading, error } = useStatements(customerId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>ລາຍການ Statement</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState message="ໂຫຼດ Statement ບໍ່ສຳເລັດ" />
        ) : !statements || statements.length === 0 ? (
          <EmptyState title="ຍັງບໍ່ມີ Statement" description="ອັບໂຫລດ PDF ເພື່ອເລີ່ມກວດສອບ" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ໄຟລ໌</TableHead>
                <TableHead>ອັບໂຫລດ</TableHead>
                <TableHead>ສະຖານະ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statements.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link
                      to="/customers/$customerId/statements/$statementId"
                      params={{ customerId, statementId: s.id }}
                      className="font-medium hover:text-primary"
                    >
                      {s.file_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(s.uploaded_at)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={s.processing_status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
