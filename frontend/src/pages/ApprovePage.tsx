import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import {
  useStatement,
  useApprovals,
  useApproveStatement,
} from "@/hooks/useStatements";
import { useRole } from "@/store/auth";
import { ApiError } from "@/lib/api";
import { formatKip, formatDate } from "@/lib/utils";
import type { ApprovalDecision } from "@/lib/types";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader, Skeleton, Spinner, EmptyState } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

const schema = z.object({
  decision: z.enum(["approved", "rejected", "partial"]),
  approved_amount: z.coerce.number().min(0, "ຈຳນວນຕ້ອງບໍ່ຕິດລົບ"),
  reason: z.string().min(1, "ກະລຸນາປ້ອນເຫດຜົນ"),
});
type FormValues = z.input<typeof schema>;

const DECISION_LABEL: Record<ApprovalDecision, string> = {
  approved: "ຜ່ານ",
  rejected: "ບໍ່ຜ່ານ",
  partial: "ຜ່ານບາງສ່ວນ",
};
const DECISION_VARIANT: Record<ApprovalDecision, "success" | "destructive" | "warning"> = {
  approved: "success",
  rejected: "destructive",
  partial: "warning",
};

export function ApprovePage({
  customerId,
  statementId,
}: {
  customerId: string;
  statementId: string;
}) {
  const role = useRole();
  const canDecide = role === "manager" || role === "admin";
  const navigate = useNavigate();

  const { data: s, isLoading } = useStatement(customerId, statementId);
  const { data: approvals } = useApprovals(customerId, statementId);
  const approve = useApproveStatement(customerId, statementId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { decision: "approved", approved_amount: 0, reason: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      await approve.mutateAsync({
        decision: values.decision,
        approved_amount: Number(values.approved_amount),
        reason: values.reason,
      });
      toast("ບັນທຶກຜົນອະນຸມັດແລ້ວ", { variant: "success" });
      navigate({
        to: "/customers/$customerId/statements/$statementId",
        params: { customerId, statementId },
      });
    } catch (err) {
      toast("ບັນທຶກບໍ່ສຳເລັດ", {
        variant: "error",
        description: err instanceof ApiError ? String(err.detail) : undefined,
      });
    }
  }

  if (isLoading) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to="/customers/$customerId/statements/$statementId"
        params={{ customerId, statementId }}
        className={buttonVariants({ variant: "ghost", size: "sm" }) + " mb-4"}
      >
        <ArrowLeft className="size-4" />
        ກັບຄືນ
      </Link>
      <PageHeader title="ອະນຸມັດ Statement" description={s?.file_name} />

      {s && (
        <Card className="mb-6">
          <CardContent className="grid grid-cols-2 gap-3 py-4 text-sm">
            <Info label="ຍອດຮັບລວມ" value={formatKip(s.total_credit)} />
            <Info label="ຍອດຈ່າຍລວມ" value={formatKip(s.total_debit)} />
            <Info label="ຈຳນວນທຸລະກຳ" value={String(s.total_transactions ?? 0)} />
            <Info
              label="ກວດສອບ"
              value={s.validation?.matched ? "ຜ່ານ" : "ບໍ່ຜ່ານ"}
            />
          </CardContent>
        </Card>
      )}

      {/* Existing decisions (visible to everyone with access, incl. officers) */}
      {approvals && approvals.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>ຜົນອະນຸມັດ</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {approvals.map((a) => (
              <div key={a.id} className="rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <Badge variant={DECISION_VARIANT[a.decision]}>{DECISION_LABEL[a.decision]}</Badge>
                  <span className="text-xs text-muted-foreground">{formatDate(a.decided_at)}</span>
                </div>
                <p className="mt-2 text-sm">ວົງເງິນ: {formatKip(a.approved_amount)}</p>
                {a.reason && <p className="mt-1 text-sm text-muted-foreground">{a.reason}</p>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {canDecide ? (
        <Card>
          <CardHeader>
            <CardTitle>ບັນທຶກການຕັດສິນໃຈ</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-1.5">
                <Label>ຜົນການພິຈາລະນາ</Label>
                <Select {...register("decision")}>
                  <option value="approved">ຜ່ານ</option>
                  <option value="partial">ຜ່ານບາງສ່ວນ</option>
                  <option value="rejected">ບໍ່ຜ່ານ</option>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>ວົງເງິນອະນຸມັດ (Kip)</Label>
                <Input type="number" step="0.01" {...register("approved_amount")} />
                {errors.approved_amount && (
                  <p className="text-xs text-destructive">{errors.approved_amount.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>ເຫດຜົນ</Label>
                <Textarea rows={4} {...register("reason")} />
                {errors.reason && <p className="text-xs text-destructive">{errors.reason.message}</p>}
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={approve.isPending}>
                  {approve.isPending && <Spinner />}
                  ບັນທຶກຜົນ
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="ອ່ານຢ່າງດຽວ"
          description="ສະເພາະ manager ຫຼື admin ເທົ່ານັ້ນທີ່ບັນທຶກຜົນອະນຸມັດໄດ້"
        />
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}
