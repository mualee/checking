import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { signInWithEmailAndPassword } from "firebase/auth";
import { useNavigate } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { auth } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/misc";

const schema = z.object({
  email: z.string().email("ອີເມວບໍ່ຖືກຕ້ອງ"),
  password: z.string().min(6, "ລະຫັດຜ່ານຢ່າງໜ້ອຍ 6 ຕົວ"),
});
type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const [authError, setAuthError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setAuthError(null);
    try {
      await signInWithEmailAndPassword(auth, values.email, values.password);
      navigate({ to: "/dashboard" });
    } catch {
      setAuthError("ອີເມວ ຫຼື ລະຫັດຜ່ານບໍ່ຖືກຕ້ອງ");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-full bg-primary/10">
            <ShieldCheck className="size-6 text-primary" />
          </div>
          <CardTitle>ລະບົບກວດສາ Statement</CardTitle>
          <CardDescription>ເຂົ້າສູ່ລະບົບເພື່ອສືບຕໍ່</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">ອີເມວ</Label>
              <Input id="email" type="email" autoComplete="email" {...register("email")} />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">ລະຫັດຜ່ານ</Label>
              <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>
            {authError && <p className="text-sm text-destructive">{authError}</p>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Spinner />}
              ເຂົ້າສູ່ລະບົບ
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
