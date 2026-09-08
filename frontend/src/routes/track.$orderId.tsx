import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { OrdersService } from "@/client"
import { PublicTopBar } from "@/components/Common/PublicTopBar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { fmtNumber } from "@/lib/format"
import { cn } from "@/lib/utils"

type Search = { phone?: string }

export const Route = createFileRoute("/track/$orderId")({
  component: TrackPage,
  validateSearch: (s: Record<string, unknown>): Search => ({
    phone: typeof s.phone === "string" ? s.phone : undefined,
  }),
})

const STEPS = [
  "pending",
  "confirmed",
  "assigned",
  "en_route",
  "delivered",
] as const

function TrackPage() {
  const { t } = useTranslation()
  const { orderId } = Route.useParams()
  const { phone: phoneParam } = Route.useSearch()
  const [phone, setPhone] = useState(phoneParam ?? "")

  const { data: order, isError } = useQuery({
    queryKey: ["order", orderId, phone],
    enabled: !!phone,
    retry: false,
    refetchInterval: 15000,
    queryFn: async () =>
      (
        await OrdersService.readOrder({
          path: { order_id: orderId },
          query: { phone },
        })
      ).data,
  })

  const currentIdx = order ? STEPS.indexOf(order.status as never) : -1

  return (
    <div>
      <PublicTopBar />
      <div className="mx-auto max-w-md p-4 md:p-8 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold">{t("track.title")}</h1>
          <p className="text-muted-foreground text-sm">
            {t("track.ref", { ref: orderId.slice(0, 8) })}
          </p>
        </div>

        {!order && (
          <Card>
            <CardHeader>
              <CardTitle>{t("track.confirmNumberTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Label>{t("track.phoneLabel")}</Label>
              <Input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+2135XXXXXXXX"
              />
              {isError && (
                <p className="text-sm text-destructive">{t("track.error")}</p>
              )}
            </CardContent>
          </Card>
        )}

        {order && (
          <Card>
            <CardContent className="flex flex-col gap-4 pt-6">
              {order.status === "cancelled" ? (
                <p className="text-destructive font-medium">
                  {order.cancelled_reason
                    ? t("track.cancelledLine", {
                        label: t("status.cancelled"),
                        reason: order.cancelled_reason,
                      })
                    : t("status.cancelled")}
                </p>
              ) : (
                <ol className="flex flex-col gap-3">
                  {STEPS.map((s, i) => (
                    <li key={s} className="flex items-center gap-3">
                      <span
                        className={cn(
                          "size-3 rounded-full",
                          i <= currentIdx
                            ? "bg-green-500"
                            : "bg-muted-foreground/30",
                        )}
                      />
                      <span
                        className={cn(
                          i === currentIdx && "font-semibold",
                          i > currentIdx && "text-muted-foreground",
                        )}
                      >
                        {t(`status.${s}`)}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
              <div className="rounded-md bg-muted p-3 text-sm">
                {t("track.cashNote", {
                  liters: order.quantity_liters,
                  total: fmtNumber(Number(order.total_price_dzd)),
                })}
              </div>
            </CardContent>
          </Card>
        )}

        <Link
          to="/"
          className="text-center text-sm underline underline-offset-4"
        >
          {t("track.newOrder")}
        </Link>
      </div>
    </div>
  )
}
