import { useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, FileText, UploadCloud, X, Building2, Printer } from "lucide-react";
import { useUploadStatement } from "@/hooks/useStatements";
import {
  BCEL_BTN_STYLE,
  JBL_BTN_STYLE,
  JDB_BTN_STYLE,
  LDB_BTN_STYLE,
} from "@/pages/CustomerDetailPage";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

type Source =
  | "digital" | "scan" | "jbl" | "jbl_scan" | "jdb" | "jdb_scan" | "ldb" | "ldb_scan";

const SOURCE_LABEL: Record<Source, string> = {
  digital: "ອັບໂຫລດ PDF ຈາກ BcelOne",
  scan: "ອັບໂຫລດ PDF ຈາກ BcelOne (Printer)",
  jbl: "ອັບໂຫລດ PDF ຈາກ JBL",
  jbl_scan: "ອັບໂຫລດ PDF ຈາກ JBL (Printer)",
  jdb: "ອັບໂຫລດ PDF ຈາກ JDB",
  jdb_scan: "ອັບໂຫລດ PDF ຈາກ JDB (Printer)",
  ldb: "ອັບໂຫລດ PDF ຈາກ LDB",
  ldb_scan: "ອັບໂຫລດ PDF ຈາກ LDB (Printer)",
};
const isScanSource = (s: Source) => s.endsWith("_scan") || s === "scan";

export function StatementNewPage({
  customerId,
  source: preselected,
}: {
  customerId: string;
  source?: Source;
}) {
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

  async function onSubmit(source: Source) {
    if (!file) return;
    try {
      const s = await upload.mutateAsync({
        file,
        openingBalance: openingBalance || undefined,
        source,
      });
      toast(
        isScanSource(source)
          ? "ອັບໂຫລດສຳເລັດ ກຳລັງອ່ານດ້ວຍ OCR..."
          : "ອັບໂຫລດສຳເລັດ ກຳລັງປະມວນຜົນ",
        { variant: "success" },
      );
      // Processing runs in the background; the detail page polls until it's done.
      navigate({
        to: "/customers/$customerId/statements/$statementId",
        params: { customerId, statementId: s.id },
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

          {preselected ? (
            <div className="pt-2">
              {(() => {
                const brand =
                  preselected === "digital" ? BCEL_BTN_STYLE :
                  preselected === "jbl" ? JBL_BTN_STYLE :
                  preselected === "jdb" ? JDB_BTN_STYLE :
                  preselected === "ldb" ? LDB_BTN_STYLE : undefined;
                return (
                  <Button
                    onClick={() => onSubmit(preselected)}
                    disabled={!file || upload.isPending}
                    variant={isScanSource(preselected) ? "secondary" : "default"}
                    className={"w-full " + (brand ? "border-0 text-white hover:opacity-90" : "")}
                    style={brand}
                  >
                    {upload.isPending ? (
                      <Spinner />
                    ) : isScanSource(preselected) ? (
                      <Printer className="size-4" />
                    ) : (
                      <Building2 className="size-4" />
                    )}
                    {SOURCE_LABEL[preselected]}
                  </Button>
                );
              })()}
            </div>
          ) : (
            <>
              <div className="grid gap-2 pt-2 sm:grid-cols-2">
                <Button
                  onClick={() => onSubmit("digital")}
                  disabled={!file || upload.isPending}
                  className="w-full border-0 text-white hover:opacity-90"
                  style={BCEL_BTN_STYLE}
                >
                  {upload.isPending ? <Spinner /> : <Building2 className="size-4" />}
                  ອັບໂຫລດ PDF ຈາກ ທະນະຄານ
                </Button>
                <Button
                  onClick={() => onSubmit("scan")}
                  disabled={!file || upload.isPending}
                  variant="secondary"
                  className="w-full"
                >
                  {upload.isPending ? <Spinner /> : <Printer className="size-4" />}
                  ອັບໂຫລດ PDF ຈາກ Printer
                </Button>
              </div>
              <p className="text-center text-xs text-muted-foreground">
                "ຈາກ ທະນະຄານ" = PDF ທີ່ມີຂໍ້ຄວາມ (ອ່ານໄວ ແມ່ນຍຳ) · "ຈາກ Printer" = ໄຟລ໌ scan (ໃຊ້ OCR)
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
