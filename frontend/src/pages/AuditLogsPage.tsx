import { useState } from "react";
import { useAuditLogs, type AuditFilters } from "@/hooks/useAuditLogs";
import { RequireRole } from "@/components/RequireRole";
import { formatDate } from "@/lib/utils";
import type { AuditAction } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Skeleton, EmptyState, ErrorState } from "@/components/ui/misc";

const ACTIONS: AuditAction[] = ["login", "upload", "process", "approve", "reject", "view", "download"];

export function AuditLogsPage() {
  return (
    <RequireRole roles={["manager", "admin"]}>
      <AuditLogsInner />
    </RequireRole>
  );
}

function AuditLogsInner() {
  const [filters, setFilters] = useState<AuditFilters>({ action: "" });
  const { data, isLoading, error } = useAuditLogs(filters);

  return (
    <div>
      <PageHeader title="ບັນທຶກການກະທຳ" description="ຄົ້ນຫາ ແລະ ກວດເບິ່ງ log ທັງໝົດ (ອ່ານຢ່າງດຽວ)" />

      <Card>
        <CardContent className="p-4">
          <div className="mb-4 grid gap-3 sm:grid-cols-4">
            <div className="space-y-1.5">
              <Label>User ID</Label>
              <Input
                value={filters.user_id ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, user_id: e.target.value }))}
                placeholder="uid"
              />
            </div>
            <div className="space-y-1.5">
              <Label>ການກະທຳ</Label>
              <Select
                value={filters.action ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value as AuditAction | "" }))}
              >
                <option value="">ທັງໝົດ</option>
                {ACTIONS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>ຈາກວັນທີ</Label>
              <Input
                type="date"
                value={filters.start ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>ຫາວັນທີ</Label>
              <Input
                type="date"
                value={filters.end ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))}
              />
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message="ໂຫຼດ log ບໍ່ສຳເລັດ" />
          ) : !data || data.length === 0 ? (
            <EmptyState title="ບໍ່ພົບ log" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ເວລາ</TableHead>
                  <TableHead>ຜູ້ໃຊ້</TableHead>
                  <TableHead>ການກະທຳ</TableHead>
                  <TableHead>ເປົ້າໝາຍ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {formatDate(log.timestamp)}
                    </TableCell>
                    <TableCell className="text-sm">{log.user_email || log.user_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{log.action}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {log.target_type}/{log.target_id}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
