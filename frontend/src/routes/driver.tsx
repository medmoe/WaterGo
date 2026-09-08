import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useCallback } from "react"
import { useTranslation } from "react-i18next"

import { DriverService, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { isLoggedIn } from "@/hooks/useAuth"
import { useLiveChannel } from "@/hooks/useLiveChannel"
import { fmtNumber } from "@/lib/format"

export const Route = createFileRoute("/driver")({
  component: Driver,
  beforeLoad: async () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" })
    const { data: me } = await UsersService.readUserMe()
    if (me.role !== "driver" && me.role !== "admin") {
      throw redirect({ to: "/" })
    }
    return { driverId: me.id }
  },
})

function Driver() {
  const { t } = useTranslation()
  const { driverId } = Route.useRouteContext()
  const qc = useQueryClient()
  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["driver", "today"] })
  }, [qc])
  useLiveChannel(`/ws/driver/${driverId}`, refresh)

  const { data: route } = useQuery({
    queryKey: ["driver", "today"],
    refetchInterval: 15000,
    retry: false,
    queryFn: async () => {
      const res = await DriverService.todaysRoute()
      return res.data ?? null
    },
  })

  const delivered = useMutation({
    mutationFn: (stopId: string) =>
      DriverService.markDelivered({ path: { stop_id: stopId } }),
    onSuccess: refresh,
  })
  const paid = useMutation({
    mutationFn: (stopId: string) =>
      DriverService.markPaymentCollected({ path: { stop_id: stopId } }),
    onSuccess: refresh,
  })

  if (!route) {
    return (
      <div className="mx-auto max-w-md p-6">
        <h1 className="text-2xl font-bold">{t("driver.title")}</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          {t("driver.noneToday")}
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md p-4 md:p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">{t("driver.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {t("driver.header", {
            date: route.planned_date,
            status: t(`routeStatus.${route.status}`, route.status),
            count: (route.stops ?? []).length,
          })}
        </p>
      </div>
      {route.status === "planned" && (
        <p className="rounded-md bg-muted p-3 text-sm">{t("driver.waiting")}</p>
      )}
      {(route.stops ?? []).map((s, i) => (
        <Card key={s.id}>
          <CardContent className="flex flex-col gap-2 py-4">
            <div className="flex items-baseline justify-between">
              <span className="font-semibold">
                {t("driver.stop", { n: i + 1 })}
              </span>
              <span className="text-xs text-muted-foreground">
                {s.delivered_at ? t("driver.delivered") : t("driver.toDeliver")}
                {s.payment_collected ? ` · ${t("driver.paidTag")}` : ""}
              </span>
            </div>
            <div className="text-sm">
              {s.order?.location?.landmark_text} — {s.order?.location?.commune}
            </div>
            <div className="text-sm text-muted-foreground">
              {t("driver.stopMeta", {
                phone: s.order?.customer_phone ?? "",
                liters: s.order?.quantity_liters ?? 0,
                total: fmtNumber(Number(s.order?.total_price_dzd ?? 0)),
              })}
            </div>
            <div className="mt-1 flex gap-2">
              <Button
                size="sm"
                disabled={!!s.delivered_at || delivered.isPending}
                onClick={() => delivered.mutate(s.id)}
              >
                {t("driver.markDelivered")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={
                  !s.delivered_at || s.payment_collected || paid.isPending
                }
                onClick={() => paid.mutate(s.id)}
              >
                {t("driver.collectCash")}
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
