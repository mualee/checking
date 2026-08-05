import { Link } from "@tanstack/react-router";
import { Users, UserPlus, ScrollText, ArrowRight } from "lucide-react";
import { useCustomers } from "@/hooks/useCustomers";
import { useAuthStore } from "@/store/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader, Skeleton } from "@/components/ui/misc";

export function DashboardPage() {
  const profile = useAuthStore((s) => s.profile);
  const { data: customers, isLoading } = useCustomers();

  const total = customers?.length ?? 0;
  const active = customers?.filter((c) => c.status === "active").length ?? 0;
  const recent = (customers ?? []).slice(0, 5);

  return (
    <div>
      <PageHeader
        title={`ສະບາຍດີ, ${profile?.name || profile?.email || ""}`}
        description="ພາບລວມຂອງລະບົບກວດສາ Statement"
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="ລູກຄ້າທັງໝົດ" value={isLoading ? undefined : total} icon={Users} />
        <StatCard label="ລູກຄ້າໃຊ້ງານຢູ່" value={isLoading ? undefined : active} icon={Users} />
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">ທາງລັດ</CardTitle>
            <ScrollText className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Link to="/customers/new" className="flex items-center gap-2 text-sm text-primary hover:underline">
              <UserPlus className="size-4" /> ເພີ່ມລູກຄ້າໃໝ່
            </Link>
            <Link to="/customers" className="flex items-center gap-2 text-sm text-primary hover:underline">
              <Users className="size-4" /> ເບິ່ງລູກຄ້າທັງໝົດ
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>ລູກຄ້າຫຼ້າສຸດ</CardTitle>
          <Link to="/customers" className="flex items-center gap-1 text-sm text-primary hover:underline">
            ທັງໝົດ <ArrowRight className="size-4" />
          </Link>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">ຍັງບໍ່ມີລູກຄ້າ</p>
          ) : (
            <ul className="divide-y">
              {recent.map((c) => (
                <li key={c.id}>
                  <Link
                    to="/customers/$customerId"
                    params={{ customerId: c.id }}
                    className="flex items-center justify-between py-3 hover:text-primary"
                  >
                    <span className="font-medium">{c.full_name}</span>
                    <span className="text-sm text-muted-foreground">{c.account_no || "-"}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | undefined;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {value === undefined ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <div className="text-3xl font-bold">{value}</div>
        )}
      </CardContent>
    </Card>
  );
}
