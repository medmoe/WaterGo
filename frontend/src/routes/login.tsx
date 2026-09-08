import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { AuthLayout } from "@/components/Common/AuthLayout"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({ to: "/" })
    }
  },
})

const phoneSchema = z.object({
  phone_number: z
    .string()
    .min(1)
    .regex(/^\+?[0-9]{6,20}$/),
})

const codeSchema = z.object({
  code: z.string().min(4).max(8),
})

function Login() {
  const { t } = useTranslation()
  const { requestOtpMutation, verifyOtpMutation } = useAuth()
  const [phone, setPhone] = useState<string | null>(null)

  const phoneForm = useForm<z.infer<typeof phoneSchema>>({
    resolver: zodResolver(phoneSchema),
    mode: "onBlur",
    defaultValues: { phone_number: "" },
  })

  const codeForm = useForm<z.infer<typeof codeSchema>>({
    resolver: zodResolver(codeSchema),
    mode: "onBlur",
    defaultValues: { code: "" },
  })

  const onRequest = phoneForm.handleSubmit((data) => {
    if (requestOtpMutation.isPending) return
    requestOtpMutation.mutate(
      { phone_number: data.phone_number },
      { onSuccess: () => setPhone(data.phone_number) },
    )
  })

  const onVerify = codeForm.handleSubmit((data) => {
    if (!phone || verifyOtpMutation.isPending) return
    verifyOtpMutation.mutate({ phone_number: phone, code: data.code })
  })

  return (
    <AuthLayout>
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold">{t("login.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {phone ? t("login.subSent", { phone }) : t("login.subDefault")}
        </p>
      </div>

      {!phone ? (
        <Form {...phoneForm}>
          <form onSubmit={onRequest} className="flex flex-col gap-6">
            <FormField
              control={phoneForm.control}
              name="phone_number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("login.phone")}</FormLabel>
                  <FormControl>
                    <Input
                      data-testid="phone-input"
                      placeholder={t("login.phonePh")}
                      type="tel"
                      autoComplete="tel"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="text-xs" />
                </FormItem>
              )}
            />
            <LoadingButton type="submit" loading={requestOtpMutation.isPending}>
              {t("login.sendCode")}
            </LoadingButton>
          </form>
        </Form>
      ) : (
        <Form {...codeForm}>
          <form onSubmit={onVerify} className="flex flex-col gap-6">
            <FormField
              control={codeForm.control}
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("login.code")}</FormLabel>
                  <FormControl>
                    <Input
                      data-testid="code-input"
                      placeholder={t("login.codePh")}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="text-xs" />
                </FormItem>
              )}
            />
            <LoadingButton type="submit" loading={verifyOtpMutation.isPending}>
              {t("login.verify")}
            </LoadingButton>
            <button
              type="button"
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
              onClick={() => {
                setPhone(null)
                codeForm.reset()
              }}
            >
              {t("login.useOther")}
            </button>
          </form>
        </Form>
      )}
    </AuthLayout>
  )
}
