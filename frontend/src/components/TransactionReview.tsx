import { useMemo, useState } from "react";
import { AlertTriangle, Save, Plus, Trash2 } from "lucide-react";
import { useTransactions, useRevalidateStatement } from "@/hooks/useStatements";
import type { Transaction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

type Row = {
  date: string;
  txnNumber: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
};

const num = (s: string) => {
  const n = parseFloat((s || "").replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
};

function toRows(txns: Transaction[]): Row[] {
  return txns.map((t) => ({
    date: t.date,
    txnNumber: t.txnNumber,
    description: t.description,
    debit: String(t.debit ?? 0),
    credit: String(t.credit ?? 0),
    balance: String(t.balance ?? 0),
  }));
}

/**
 * Review & correct extracted transactions (mainly OCR output) before re-running
 * validation. Rows whose running balance doesn't reconcile are highlighted so the
 * reviewer can fix the misread cell, then Save re-validates and builds the report.
 */
export function TransactionReview({
  customerId,
  statementId,
  mismatchCount,
}: {
  customerId: string;
  statementId: string;
  mismatchCount?: number;
}) {
  const { data, isLoading } = useTransactions(customerId, statementId, true);
  const revalidate = useRevalidateStatement(customerId, statementId);
  const [rows, setRows] = useState<Row[] | null>(null);

  const current = rows ?? (data ? toRows(data) : null);

  // Running-balance reconciliation, recomputed live as the reviewer edits.
  const badRows = useMemo(() => {
    const bad = new Set<number>();
    if (!current || current.length === 0) return bad;
    const opening = num(current[0].balance) - num(current[0].credit) + num(current[0].debit);
    let prev = opening;
    current.forEach((r, i) => {
      const expected = prev + num(r.credit) - num(r.debit);
      if (Math.abs(expected - num(r.balance)) > 0.005) bad.add(i);
      prev = num(r.balance);
    });
    return bad;
  }, [current]);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!current) return null;

  function withRows(fn: (rows: Row[]) => Row[]) {
    setRows((prevRows) => fn((prevRows ?? toRows(data ?? [])).slice()));
  }

  function edit(i: number, field: keyof Row, value: string) {
    withRows((rs) => {
      rs[i] = { ...rs[i], [field]: value };
      return rs;
    });
  }

  // OCR can miss a whole transaction; let the reviewer insert one (seeded with the
  // previous row's date to save typing) or delete a spurious one.
  function insertAfter(i: number) {
    withRows((rs) => {
      const prev = rs[i];
      rs.splice(i + 1, 0, {
        date: prev?.date ?? "",
        txnNumber: "",
        description: "",
        debit: "0",
        credit: "0",
        balance: prev?.balance ?? "0",
      });
      return rs;
    });
  }

  function removeRow(i: number) {
    withRows((rs) => {
      rs.splice(i, 1);
      return rs;
    });
  }

  function save() {
    const payload: Transaction[] = current!.map((r) => ({
      date: r.date,
      txnNumber: r.txnNumber,
      description: r.description,
      debit: num(r.debit),
      credit: num(r.credit),
      balance: num(r.balance),
    }));
    revalidate.mutate(payload, {
      onSuccess: (s) => {
        if (s.processing_status === "completed") {
          toast("ກວດສອບຜ່ານ — ອອກລາຍງານແລ້ວ", { variant: "success" });
        } else {
          toast("ບັນທຶກແລ້ວ ແຕ່ຍັງມີແຖວທີ່ຄາດເຄື່ອນ", { variant: "error" });
        }
      },
      onError: () => toast("ບັນທຶກບໍ່ສຳເລັດ", { variant: "error" }),
    });
  }

  return (
    <Card className="border-amber-500/40">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-amber-500" />
            ກວດ/ແກ້ຂໍ້ມູນທີ່ອ່ານຈາກ scan
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {typeof mismatchCount === "number" && mismatchCount > 0
              ? `ພົບ ${mismatchCount} ແຖວທີ່ຍອດຄົງເຫຼືອບໍ່ກົງ — ແກ້ຄ່າທີ່ໄຮໄລໃຫ້ຖືກ ແລ້ວກົດບັນທຶກ`
              : "ກວດຄ່າໃຫ້ຖືກ ແລ້ວກົດບັນທຶກເພື່ອອອກລາຍງານ"}
            {" · "}
            <span className="text-amber-600">{badRows.size}</span> ແຖວຍັງບໍ່ກົງ
          </p>
        </div>
        <Button onClick={save} disabled={revalidate.isPending}>
          {revalidate.isPending ? <Spinner className="size-4" /> : <Save className="size-4" />}
          ບັນທຶກ & ກວດຄືນ
        </Button>
      </CardHeader>
      <CardContent>
        <div className="max-h-[70vh] overflow-auto">
          <Table>
            <TableHeader className="sticky top-0 bg-card">
              <TableRow>
                <TableHead className="w-24">ວັນທີ</TableHead>
                <TableHead>ເລກບີນ</TableHead>
                <TableHead className="text-right">ໜີ້</TableHead>
                <TableHead className="text-right">ມີ</TableHead>
                <TableHead className="text-right">ຍອດຄົງເຫຼືອ</TableHead>
                <TableHead className="w-20 text-center">ຈັດການ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {current.map((r, i) => {
                const bad = badRows.has(i);
                return (
                  <TableRow key={i} className={bad ? "bg-destructive/5" : undefined}>
                    <TableCell>
                      <input
                        value={r.date}
                        onChange={(e) => edit(i, "date", e.target.value)}
                        className="w-24 rounded border border-input bg-background px-2 py-1 text-sm"
                      />
                    </TableCell>
                    <TableCell>
                      <input
                        value={r.txnNumber}
                        onChange={(e) => edit(i, "txnNumber", e.target.value)}
                        className="w-full min-w-[7rem] rounded border border-input bg-background px-2 py-1 text-sm"
                      />
                    </TableCell>
                    {(["debit", "credit", "balance"] as const).map((f) => (
                      <TableCell key={f} className="text-right">
                        <input
                          value={r[f]}
                          inputMode="decimal"
                          onChange={(e) => edit(i, f, e.target.value)}
                          className={
                            "w-32 rounded border bg-background px-2 py-1 text-right text-sm " +
                            (bad && f === "balance"
                              ? "border-destructive text-destructive"
                              : "border-input")
                          }
                        />
                      </TableCell>
                    ))}
                    <TableCell>
                      <div className="flex justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7"
                          title="ເພີ່ມແຖວໃໝ່ຂ້າງລຸ່ມ"
                          onClick={() => insertAfter(i)}
                        >
                          <Plus className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-destructive hover:text-destructive"
                          title="ລຶບແຖວນີ້"
                          onClick={() => removeRow(i)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => insertAfter(current.length - 1)}
          >
            <Plus className="size-4" />
            ເພີ່ມແຖວ
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
