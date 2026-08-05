import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { updatePassword } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

const pwSchema = z
  .object({
    password: z.string().min(6, "ລະຫັດຜ່ານໃໝ່ຢ່າງໜ້ອຍ 6 ຕົວ"),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "ລະຫັດຜ່ານບໍ່ກົງກັນ",
  });
type PwValues = z.infer<typeof pwSchema>;

export function SettingsPage() {
  const profile = useAuthStore((s) => s.profile);
  const [language, setLanguage] = useState(() => localStorage.getItem("lang") ?? "lo");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PwValues>({ resolver: zodResolver(pwSchema) });

  async function onChangePassword(values: PwValues) {
    if (!auth.currentUser) return;
    try {
      await updatePassword(auth.currentUser, values.password);
      toast("ປ່ຽນລະຫັດຜ່ານສຳເລັດ", { variant: "success" });
      reset();
    } catch {
      toast("ປ່ຽນລະຫັດຜ່ານບໍ່ສຳເລັດ", {
        variant: "error",
        description: "ອາດຕ້ອງເຂົ້າສູ່ລະບົບໃໝ່ກ່ອນປ່ຽນລະຫັດຜ່ານ",
      });
    }
  }

  function saveLanguage(value: string) {
    setLanguage(value);
    localStorage.setItem("lang", value);
    toast("ບັນທຶກພາສາແລ້ວ", { variant: "success" });
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="ຕັ້ງຄ່າສ່ວນຕົວ" description="ຈັດການບັນຊີ ແລະ ການສະແດງຜົນ" />

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>ຂໍ້ມູນບັນຊີ</CardTitle>
            <CardDescription>ຂໍ້ມູນຜູ້ໃຊ້ປັດຈຸບັນ</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <div className="flex justify-between border-b py-2">
              <span className="text-muted-foreground">ຊື່</span>
              <span className="font-medium">{profile?.name || "-"}</span>
            </div>
            <div className="flex justify-between border-b py-2">
              <span className="text-muted-foreground">ອີເມວ</span>
              <span className="font-medium">{profile?.email}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-muted-foreground">ພະແນກ</span>
              <span className="font-medium">{profile?.department || "-"}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>ປ່ຽນລະຫັດຜ່ານ</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onChangePassword)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="password">ລະຫັດຜ່ານໃໝ່</Label>
                <Input id="password" type="password" {...register("password")} />
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirm">ຢືນຢັນລະຫັດຜ່ານ</Label>
                <Input id="confirm" type="password" {...register("confirm")} />
                {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
              </div>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Spinner />}
                ບັນທຶກ
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>ພາສາສະແດງຜົນ</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-w-xs space-y-1.5">
              <Label htmlFor="lang">ພາສາ</Label>
              <Select id="lang" value={language} onChange={(e) => saveLanguage(e.target.value)}>
                <option value="lo">ລາວ</option>
                <option value="en">English</option>
              </Select>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
