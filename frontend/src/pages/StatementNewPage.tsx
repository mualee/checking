import { useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, FileText, UploadCloud, X } from "lucide-react";
import { useUploadStatement } from "@/hooks/useStatements";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

export function StatementNewPage({ customerId }: { customerId: string }) {
  const navigate = useNavigate();
  const upload = useUploadStatement(customerId);
  const [file, setFile] = useState<File | null>(null);
  const [openingBalance, setOpeningBalance] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | null) {
    if (f && f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
      toast("ຮອງຮັບສະເພາະໄຟລ໌ PDF", { variant: "error" });
      return;
    }
    setFile(f);
  }

  async function onSubmit() {
    if (!file) return;
    try {
      const statement = await upload.mutateAsync({
        file,
        openingBalance: openingBalance || undefined,
      });
      toast("ອັບໂຫລດສຳເລັດ ກຳລັງປະມວນຜົນ", { variant: "success" });
      navigate({
        to: "/customers/$customerId/statements/$statementId",
        params: { customerId, statementId: statement.id },
      });
    } catch (err) {
      toast("ອັບໂຫລດບໍ່ສຳເລັດ", {
        variant: "error",
        description: err instanceof ApiError ? String(err.detail) : undefined,
      });
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to="/customers/$customerId"
        params={{ customerId }}
        className={buttonVariants({ variant: "ghost", size: "sm" }) + " mb-4"}
      >
        <ArrowLeft className="size-4" />
        ກັບຄືນ
      </Link>
      <PageHeader title="ອັບໂຫລດ Statement ໃໝ່" description="ອັບໂຫລດໄຟລ໌ PDF ເພື່ອກວດສອບອັດຕະໂນມັດ" />

      <Card>
        <CardContent className="space-y-4 p-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pick(e.dataTransfer.files?.[0] ?? null);
            }}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors",
              dragOver ? "border-primary bg-primary/5" : "border-input hover:bg-accent/50"
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
            <UploadCloud className="mb-3 size-10 text-muted-foreground" />
            <p className="font-medium">ລາກໄຟລ໌ມາໃສ່ ຫຼື ຄລິກເພື່ອເລືອກ</p>
            <p className="mt-1 text-sm text-muted-foreground">ຮອງຮັບໄຟລ໌ PDF ເທົ່ານັ້ນ</p>
          </div>

          {file && (
            <div className="flex items-center gap-3 rounded-md border bg-muted/40 p-3">
              <FileText className="size-5 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setFile(null)}>
                <X className="size-4" />
              </Button>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="ob">ຍອດເງິນຕົ້ນງວດ (ຖ້າຮູ້)</Label>
            <Input
              id="ob"
              inputMode="decimal"
              placeholder="ປ່ອຍວ່າງເພື່ອຄິດໄລ່ຈາກແຖວທຳອິດ"
              value={openingBalance}
              onChange={(e) => setOpeningBalance(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              ຖ້າບໍ່ປ້ອນ ລະບົບຈະຄິດໄລ່ຍອດຕົ້ນງວດຈາກທຸລະກຳລາຍການທຳອິດ.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={onSubmit} disabled={!file || upload.isPending}>
              {upload.isPending && <Spinner />}
              ອັບໂຫລດ ແລະ ປະມວນຜົນ
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
