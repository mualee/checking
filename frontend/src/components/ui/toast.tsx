import { create } from "zustand";
import { CheckCircle2, XCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";
interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = Date.now() + Math.random();
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })), 4500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

export function toast(title: string, opts?: { description?: string; variant?: ToastVariant }) {
  useToastStore.getState().push({
    title,
    description: opts?.description,
    variant: opts?.variant ?? "info",
  });
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "flex items-start gap-3 rounded-lg border bg-card p-4 shadow-lg",
            t.variant === "error" && "border-destructive/40",
            t.variant === "success" && "border-emerald-500/40"
          )}
        >
          {t.variant === "success" && <CheckCircle2 className="mt-0.5 size-5 text-emerald-500" />}
          {t.variant === "error" && <XCircle className="mt-0.5 size-5 text-destructive" />}
          <div className="flex-1">
            <p className="text-sm font-medium">{t.title}</p>
            {t.description && <p className="mt-0.5 text-sm text-muted-foreground">{t.description}</p>}
          </div>
          <button onClick={() => dismiss(t.id)} className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
