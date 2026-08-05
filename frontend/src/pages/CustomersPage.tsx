import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Search, UserPlus } from "lucide-react";
import { useCustomers } from "@/hooks/useCustomers";
import { ApiError } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Skeleton, EmptyState, ErrorState } from "@/components/ui/misc";

export function CustomersPage() {
  const { data, isLoading, error } = useCustomers();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("all");

  const filtered = useMemo(() => {
    const list = data ?? [];
    return list.filter((c) => {
      const matchesQuery =
        !query ||
        c.full_name.toLowerCase().includes(query.toLowerCase()) ||
        (c.account_no ?? "").toLowerCase().includes(query.toLowerCase()) ||
        (c.phone ?? "").includes(query);
      const matchesStatus = status === "all" || c.status === status;
      return matchesQuery && matchesStatus;
    });
  }, [data, query, status]);

  return (
    <div>
      <PageHeader title="ລູກຄ້າ" description="ຄົ້ນຫາ ແລະ ຈັດການລູກຄ້າ">
        <Link to="/customers/new" className={buttonVariants()}>
          <UserPlus className="size-4" />
          ເພີ່ມລູກຄ້າ
        </Link>
      </PageHeader>

      <Card>
        <CardContent className="p-4">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="ຄົ້ນຫາຊື່, ບັນຊີ, ເບີໂທ..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="sm:w-48">
              <option value="all">ທຸກສະຖານະ</option>
              <option value="active">ໃຊ້ງານ</option>
              <option value="archived">ຈັດເກັບ</option>
            </Select>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState
              message={error instanceof ApiError ? String(error.detail) : "ໂຫຼດຂໍ້ມູນບໍ່ສຳເລັດ"}
            />
          ) : filtered.length === 0 ? (
            <EmptyState title="ບໍ່ພົບລູກຄ້າ" description="ລອງປັບການຄົ້ນຫາ ຫຼື ເພີ່ມລູກຄ້າໃໝ່" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ຊື່</TableHead>
                  <TableHead>ເລກບັນຊີ</TableHead>
                  <TableHead>ເບີໂທ</TableHead>
                  <TableHead>ສະຖານະ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((c) => (
                  <TableRow key={c.id} className="cursor-pointer">
                    <TableCell>
                      <Link
                        to="/customers/$customerId"
                        params={{ customerId: c.id }}
                        className="font-medium hover:text-primary"
                      >
                        {c.full_name}
                      </Link>
                    </TableCell>
                    <TableCell>{c.account_no || "-"}</TableCell>
                    <TableCell>{c.phone || "-"}</TableCell>
                    <TableCell>
                      <Badge variant={c.status === "active" ? "success" : "secondary"}>
                        {c.status === "active" ? "ໃຊ້ງານ" : "ຈັດເກັບ"}
                      </Badge>
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
