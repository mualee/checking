import type { ReactNode } from "react";
import { useRole } from "@/store/auth";
import type { Role } from "@/lib/types";
import { EmptyState } from "@/components/ui/misc";

/** Renders children only if the current user's role is allowed. */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const role = useRole();
  if (!role || !roles.includes(role)) {
    return (
      <EmptyState
        title="ບໍ່ມີສິດເຂົ້າເຖິງ"
        description="ໜ້ານີ້ອະນຸຍາດສະເພາະບາງ role ເທົ່ານັ້ນ."
      />
    );
  }
  return <>{children}</>;
}
