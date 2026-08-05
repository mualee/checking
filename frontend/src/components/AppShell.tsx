import { useState } from "react";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { signOut } from "firebase/auth";
import {
  LayoutDashboard,
  Users,
  ScrollText,
  UserCog,
  Settings,
  LogOut,
  Menu,
  ShieldCheck,
} from "lucide-react";
import { auth } from "@/lib/firebase";
import { useAuthStore } from "@/store/auth";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: Role[];
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "ໜ້າຫຼັກ", icon: LayoutDashboard, roles: ["officer", "manager", "admin"] },
  { to: "/customers", label: "ລູກຄ້າ", icon: Users, roles: ["officer", "manager", "admin"] },
  { to: "/audit-logs", label: "ບັນທຶກການກະທຳ", icon: ScrollText, roles: ["manager", "admin"] },
  { to: "/users", label: "ຈັດການຜູ້ໃຊ້", icon: UserCog, roles: ["admin"] },
  { to: "/settings", label: "ຕັ້ງຄ່າ", icon: Settings, roles: ["officer", "manager", "admin"] },
];

const ROLE_LABEL: Record<Role, string> = {
  officer: "ພະນັກງານ",
  manager: "ຜູ້ຈັດການ",
  admin: "ຜູ້ດູແລລະບົບ",
};

export function AppShell() {
  const profile = useAuthStore((s) => s.profile);
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const role = profile?.role;
  const items = NAV.filter((n) => role && n.roles.includes(role));

  async function handleLogout() {
    await signOut(auth);
    navigate({ to: "/login" });
  }

  return (
    <div className="flex min-h-screen bg-muted/30">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 border-r bg-card transition-transform md:static md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b px-5">
          <ShieldCheck className="size-6 text-primary" />
          <span className="font-semibold leading-tight">ກວດສາ Statement</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {items.map((item) => {
            const active = pathname === item.to || pathname.startsWith(item.to + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-primary text-primary-foreground" : "hover:bg-accent"
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between gap-4 border-b bg-card px-4 md:px-6">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)}>
            <Menu className="size-5" />
          </Button>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium leading-tight">{profile?.name || profile?.email}</p>
              {role && (
                <Badge variant="secondary" className="mt-0.5">
                  {ROLE_LABEL[role]}
                </Badge>
              )}
            </div>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              <LogOut className="size-4" />
              ອອກຈາກລະບົບ
            </Button>
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
