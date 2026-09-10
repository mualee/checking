import { useState } from "react";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { logout } from "@/lib/authClient";
import {
  LayoutDashboard,
  Users,
  ScrollText,
  UserCog,
  Settings,
  LogOut,
  ShieldCheck,
  Sun,
  Moon,
} from "lucide-react";
import { getTheme, toggleTheme, type Theme } from "@/lib/theme";
import { useAuthStore } from "@/store/auth";
import type { Role } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

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

function AppSidebar() {
  const profile = useAuthStore((s) => s.profile);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { setOpenMobile, isMobile } = useSidebar();

  const role = profile?.role;
  const items = NAV.filter((n) => role && n.roles.includes(role));

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex h-10 items-center gap-2 px-2">
          <ShieldCheck className="size-6 shrink-0 text-sidebar-primary" />
          <span className="truncate font-semibold group-data-[collapsible=icon]:hidden">
            ກວດສາ Statement
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {items.map((item) => {
              const active = pathname === item.to || pathname.startsWith(item.to + "/");
              const Icon = item.icon;
              return (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                    <Link to={item.to} onClick={() => isMobile && setOpenMobile(false)}>
                      <Icon className="size-4" />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter />
      <SidebarRail />
    </Sidebar>
  );
}

export function AppShell() {
  const profile = useAuthStore((s) => s.profile);
  const navigate = useNavigate();
  const [theme, setTheme] = useState<Theme>(getTheme());
  const role = profile?.role;

  function handleLogout() {
    logout();
    useAuthStore.getState().reset();
    navigate({ to: "/login" });
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-card px-4 md:px-6">
          <SidebarTrigger />
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium leading-tight">{profile?.name || profile?.email}</p>
              {role && (
                <Badge variant="secondary" className="mt-0.5">
                  {ROLE_LABEL[role]}
                </Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(toggleTheme())}
              aria-label={theme === "dark" ? "ໂໝດແຈ້ງ" : "ໂໝດມືດ"}
              title={theme === "dark" ? "ໂໝດແຈ້ງ" : "ໂໝດມືດ"}
            >
              {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
            </Button>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              <LogOut className="size-4" />
              ອອກຈາກລະບົບ
            </Button>
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
