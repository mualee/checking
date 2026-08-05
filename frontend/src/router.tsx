import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  Outlet,
  useParams,
} from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { AuthGate, RedirectIfAuthed } from "@/components/guards";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CustomersPage } from "@/pages/CustomersPage";
import { CustomerNewPage } from "@/pages/CustomerNewPage";
import { CustomerDetailPage } from "@/pages/CustomerDetailPage";
import { StatementNewPage } from "@/pages/StatementNewPage";
import { StatementDetailPage } from "@/pages/StatementDetailPage";
import { ApprovePage } from "@/pages/ApprovePage";
import { AuditLogsPage } from "@/pages/AuditLogsPage";
import { UsersPage } from "@/pages/UsersPage";
import { SettingsPage } from "@/pages/SettingsPage";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: () => (
    <RedirectIfAuthed>
      <LoginPage />
    </RedirectIfAuthed>
  ),
});

// Pathless layout route: enforces auth and renders the AppShell around all app pages.
const appLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  component: () => (
    <AuthGate>
      <AppShell />
    </AuthGate>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/dashboard" });
  },
});

const dashboardRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/dashboard",
  component: DashboardPage,
});

const customersRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers",
  component: CustomersPage,
});

const customerNewRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers/new",
  component: CustomerNewPage,
});

const customerDetailRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers/$customerId",
  component: function CustomerDetailRouteCmp() {
    const { customerId } = useParams({ strict: false });
    return <CustomerDetailPage customerId={customerId!} />;
  },
});

const statementNewRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers/$customerId/statements/new",
  component: function StatementNewRouteCmp() {
    const { customerId } = useParams({ strict: false });
    return <StatementNewPage customerId={customerId!} />;
  },
});

const statementDetailRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers/$customerId/statements/$statementId",
  component: function StatementDetailRouteCmp() {
    const { customerId, statementId } = useParams({ strict: false });
    return <StatementDetailPage customerId={customerId!} statementId={statementId!} />;
  },
});

const approveRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/customers/$customerId/statements/$statementId/approve",
  component: function ApproveRouteCmp() {
    const { customerId, statementId } = useParams({ strict: false });
    return <ApprovePage customerId={customerId!} statementId={statementId!} />;
  },
});

const auditLogsRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/audit-logs",
  component: AuditLogsPage,
});

const usersRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/users",
  component: UsersPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/settings",
  component: SettingsPage,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  appLayoutRoute.addChildren([
    indexRoute,
    dashboardRoute,
    customersRoute,
    customerNewRoute,
    customerDetailRoute,
    statementNewRoute,
    statementDetailRoute,
    approveRoute,
    auditLogsRoute,
    usersRoute,
    settingsRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
