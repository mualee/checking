import { Link } from "@tanstack/react-router";
import { ArrowLeft, Download, CheckCircle2, AlertTriangle, ClipboardCheck } from "lucide-react";
import { useStatement, useTransactions, useDownloadReport } from "@/hooks/useStatements";
import { useRole } from "@/store/auth";
import { ApiError } from "@/lib/api";
import { formatKip } from "@/lib/utils";
import type { Statement } from "@/lib/types";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader, Skeleton, ErrorState, EmptyState, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

export function StatementDetailPage({
  customerId,
  statementId,
}: {
  customerId: string;
  statementId: string;
}) {
  const { data: s, isLoading, error } = useStatement(customerId, statementId);
  const role = useRole();
  const canApprove = role === "manager" || role === "admin";

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error)
    return <ErrorState message={error instanceof ApiError ? String(error.detail) : "ໂຫຼດບໍ່ສຳເລັດ"} />;
  if (!s) return <EmptyState title="ບໍ່ພົບ Statement" />;

  const processing = s.processing_status === "processing" || s.processing_status === "pending";
  const completed = s.processing_status === "completed";

  return (
    <div>
      <Link
        to="/customers/$customerId"
        params={{ customerId }}
        className={buttonVariants({ variant: "ghost", size: "sm" }) + " mb-4"}
      >
        <ArrowLeft className="size-4" />
        ກັບຄືນ
      </Link>
      <PageHeader title={s.file_name} description={`ໄລຍະ: ${s.period_start || "?"} - ${s.period_end || "?"}`}>
        <StatusBadge status={s.processing_status} />
        {completed && <ReportButton customerId={customerId} statementId={statementId} />}
        {completed && canApprove && (
          <Link
            to="/customers/$customerId/statements/$statementId/approve"
            params={{ customerId, statementId }}
            className={buttonVariants({ variant: "default" })}
          >
            <ClipboardCheck className="size-4" />
            ອະນຸມັດ
          </Link>
        )}
      </PageHeader>

      {processing && (
        <Card className="mb-6">
          <CardContent className="flex items-center gap-3 py-6">
            <Spinner className="size-5" />
            <p className="text-sm">ກຳລັງປະມວນຜົນ... ໜ້ານີ້ຈະອັບເດດອັດຕະໂນມັດ</p>
          </CardContent>
        </Card>
      )}

      <ValidationCard statement={s} />

      {completed && (
        <div className="mt-6 grid gap-6">
          <Table1Card statement={s} />
          <Table2Card statement={s} />
          <Table3Card statement={s} />
          <TransactionsCard customerId={customerId} statementId={statementId} enabled={completed} />
        </div>
      )}
    </div>
  );
}

function ValidationCard({ statement: s }: { statement: Statement }) {
  if (s.processing_status === "error") {
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex items-start gap-3 py-4">
          <AlertTriangle className="mt-0.5 size-5 text-destructive" />
          <div>
            <p className="font-medium text-destructive">ປະມວນຜົນຜິດພາດ</p>
            <p className="text-sm text-muted-foreground">{s.error_detail || "ບໍ່ສາມາດອ່ານໄຟລ໌ໄດ້"}</p>
          </div>
        </CardContent>
      </Card>
    );
  }
  if (!s.validation) return null;
  const ok = s.validation.matched;
  return (
    <Card className={ok ? "border-emerald-500/40" : "border-destructive/40"}>
      <CardContent className="flex items-start gap-3 py-4">
        {ok ? (
          <CheckCircle2 className="mt-0.5 size-5 text-emerald-500" />
        ) : (
          <AlertTriangle className="mt-0.5 size-5 text-destructive" />
        )}
        <div>
          <p className={"font-medium " + (ok ? "text-emerald-600" : "text-destructive")}>
            {ok ? "ກວດສອບຄວາມຖືກຕ້ອງຜ່ານ" : "ພົບຄວາມຄາດເຄື່ອນ"}
          </p>
          <p className="text-sm text-muted-foreground">
            {ok
              ? "ຍອດຄົງເຫຼືອທຸກແຖວກົງກັບການຄິດໄລ່ຄືນ"
              : `ພົບ ${s.validation.mismatchCount} ແຖວທີ່ຄາດເຄື່ອນ — ບໍ່ອອກລາຍງານ`}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function Table1Card({ statement: s }: { statement: Statement }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>ຕາຕະລາງ 1: ສະຫຼຸບຕໍ່ເດືອນ</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ເດືອນ</TableHead>
              <TableHead className="text-right">ໜີ້</TableHead>
              <TableHead className="text-right">ມີ</TableHead>
              <TableHead className="text-right">ສ່ວນຕ່າງ</TableHead>
              <TableHead className="text-right">ຍອດເຫຼືອທ້າຍເດືອນ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {s.table1Summary.map((r, i) => {
              const isTotal = i === s.table1Summary.length - 1;
              return (
                <TableRow key={r.month + i} className={isTotal ? "bg-amber-50 font-semibold dark:bg-amber-950/30" : ""}>
                  <TableCell>{r.month}</TableCell>
                  <TableCell className="text-right">{formatKip(r.debit)}</TableCell>
                  <TableCell className="text-right">{formatKip(r.credit)}</TableCell>
                  <TableCell className="text-right">{formatKip(r.diff)}</TableCell>
                  <TableCell className="text-right">{formatKip(r.endBalance)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Table2Card({ statement: s }: { statement: Statement }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>ຕາຕະລາງ 2: 3 ເດືອນທຸລະກຳຮັບສູງສຸດ</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ເດືອນ</TableHead>
              <TableHead className="text-right">ໜີ້</TableHead>
              <TableHead className="text-right">ມີ</TableHead>
              <TableHead className="text-right">ສ່ວນຕ່າງ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {s.table2Summary.map((r, i) => (
              <TableRow key={r.month + i}>
                <TableCell>{r.month}</TableCell>
                <TableCell className="text-right">{formatKip(r.debit)}</TableCell>
                <TableCell className="text-right">{formatKip(r.credit)}</TableCell>
                <TableCell className="text-right">{formatKip(r.diff)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Table3Card({ statement: s }: { statement: Statement }) {
  const groups = s.table3Summary ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>ຕາຕະລາງ 3: ລາຍຈ່າຍປະຈຳ (ຕິດຕໍ່ກັນ 3 ເດືອນຂຶ້ນໄປ)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {groups.length === 0 ? (
          <EmptyState title="ບໍ່ພົບລາຍຈ່າຍປະຈຳ" description="ບໍ່ມີຈຳນວນເງິນທີ່ຈ່າຍເທົ່າກັນຕິດຕໍ່ກັນ 3 ເດືອນຂຶ້ນໄປ" />
        ) : (
          groups.map((g, gi) => (
            <div key={gi}>
              <div className="mb-2 flex items-center gap-2">
                <span className="font-semibold">{formatKip(g.amount)}</span>
                <Badge variant="warning">ຕິດຕໍ່ກັນ {g.monthCount} ເດືອນ</Badge>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ເດືອນ</TableHead>
                    <TableHead>ເລກທີ</TableHead>
                    <TableHead className="text-right">ໜີ້</TableHead>
                    <TableHead>ລາຍລະອຽດ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {g.rows.map((r, ri) => (
                    <TableRow key={ri}>
                      <TableCell>{r.month}</TableCell>
                      <TableCell>{r.txnNumber}</TableCell>
                      <TableCell className="text-right">{formatKip(r.debit)}</TableCell>
                      <TableCell className="max-w-xs truncate">{r.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function TransactionsCard({
  customerId,
  statementId,
  enabled,
}: {
  customerId: string;
  statementId: string;
  enabled: boolean;
}) {
  const { data: txns, isLoading } = useTransactions(customerId, statementId, enabled);
  return (
    <Card>
      <CardHeader>
        <CardTitle>ລາຍລະອຽດທຸລະກຳ {txns ? `(${txns.length})` : ""}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : !txns || txns.length === 0 ? (
          <EmptyState title="ບໍ່ມີຂໍ້ມູນທຸລະກຳ" />
        ) : (
          <div className="max-h-[28rem] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ວັນທີ</TableHead>
                  <TableHead>ເລກທີ</TableHead>
                  <TableHead>ລາຍລະອຽດ</TableHead>
                  <TableHead className="text-right">ໜີ້</TableHead>
                  <TableHead className="text-right">ມີ</TableHead>
                  <TableHead className="text-right">ຍອດເຫຼືອ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {txns.map((t, i) => (
                  <TableRow key={i}>
                    <TableCell className="whitespace-nowrap">{t.date}</TableCell>
                    <TableCell>{t.txnNumber}</TableCell>
                    <TableCell className="max-w-xs truncate">{t.description}</TableCell>
                    <TableCell className="text-right">{t.debit ? formatKip(t.debit) : "-"}</TableCell>
                    <TableCell className="text-right">{t.credit ? formatKip(t.credit) : "-"}</TableCell>
                    <TableCell className="text-right">{formatKip(t.balance)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ReportButton({ customerId, statementId }: { customerId: string; statementId: string }) {
  const report = useDownloadReport(customerId, statementId);
  async function download() {
    try {
      await report.mutateAsync();
    } catch {
      toast("ດາວໂຫລດບໍ່ສຳເລັດ", { variant: "error" });
    }
  }
  return (
    <Button variant="outline" onClick={download} disabled={report.isPending}>
      {report.isPending ? <Spinner /> : <Download className="size-4" />}
      ດາວໂຫລດ Word
    </Button>
  );
}
