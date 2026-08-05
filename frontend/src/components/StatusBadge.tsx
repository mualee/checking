import { Badge } from "@/components/ui/badge";
import type { ProcessingStatus } from "@/lib/types";

const MAP: Record<ProcessingStatus, { label: string; variant: "default" | "secondary" | "destructive" | "success" | "warning" }> = {
  pending: { label: "ລໍຖ້າ", variant: "secondary" },
  processing: { label: "ກຳລັງປະມວນຜົນ", variant: "warning" },
  validated: { label: "ກວດແລ້ວ", variant: "default" },
  validation_failed: { label: "ກວດສອບບໍ່ຜ່ານ", variant: "destructive" },
  completed: { label: "ສຳເລັດ", variant: "success" },
  error: { label: "ຜິດພາດ", variant: "destructive" },
};

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const s = MAP[status] ?? { label: status, variant: "secondary" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}
