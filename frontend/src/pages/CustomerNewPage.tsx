import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useCreateCustomer } from "@/hooks/useCustomers";
import { ApiError } from "@/lib/api";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, Spinner } from "@/components/ui/misc";
import { toast } from "@/components/ui/toast";

const schema = z.object({
  full_name: z.string().min(1, "ກະລຸນາປ້ອນຊື່"),
  national_id: z.string().optional(),
  phone: z.string().optional(),
  account_no: z.string().optional(),
  address: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export function CustomerNewPage() {
  const navigate = useNavigate();
  const create = useCreateCustomer();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      const customer = await create.mutateAsync(values);
      toast("ສ້າງລູກຄ້າສຳເລັດ", { variant: "success" });
      navigate({ to: "/customers/$customerId", params: { customerId: customer.id } });
    } catch (err) {
      toast("ສ້າງລູກຄ້າບໍ່ສຳເລັດ", {
        variant: "error",
        description: err instanceof ApiError ? String(err.detail) : undefined,
      });
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link to="/customers" className={buttonVariants({ variant: "ghost", size: "sm" }) + " mb-4"}>
        <ArrowLeft className="size-4" />
        ກັບຄືນ
      </Link>
      <PageHeader title="ເພີ່ມລູກຄ້າໃໝ່" />

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Field label="ຊື່ ແລະ ນາມສະກຸນ *" error={errors.full_name?.message}>
              <Input {...register("full_name")} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="ເລກບັດປະຈຳຕົວ" error={errors.national_id?.message}>
                <Input {...register("national_id")} />
              </Field>
              <Field label="ເບີໂທ" error={errors.phone?.message}>
                <Input {...register("phone")} />
              </Field>
            </div>
            <Field label="ເລກບັນຊີ" error={errors.account_no?.message}>
              <Input {...register("account_no")} />
            </Field>
            <Field label="ທີ່ຢູ່" error={errors.address?.message}>
              <Input {...register("address")} />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Link to="/customers" className={buttonVariants({ variant: "outline" })}>
                ຍົກເລີກ
              </Link>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending && <Spinner />}
                ບັນທຶກ
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
