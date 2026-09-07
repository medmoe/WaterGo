import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useCallback } from "react"

import { DriverService, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { isLoggedIn } from "@/hooks/useAuth"
import { useLiveChannel } from "@/hooks/useLiveChannel"

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
  head: () => ({ meta: [{ title: "Ma tournée" }] }),
})

function Driver() {
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
        <h1 className="text-2xl font-bold">Ma tournée</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Aucune tournée pour aujourd'hui.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md p-4 md:p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">Ma tournée</h1>
        <p className="text-muted-foreground text-sm">
          {route.planned_date} · {route.status} · {(route.stops ?? []).length}{" "}
          arrêts
        </p>
      </div>
      {route.status === "planned" && (
        <p className="rounded-md bg-muted p-3 text-sm">
          En attente du démarrage par le dispatch.
        </p>
      )}
      {(route.stops ?? []).map((s, i) => (
        <Card key={s.id}>
          <CardContent className="flex flex-col gap-2 py-4">
            <div className="flex items-baseline justify-between">
              <span className="font-semibold">Arrêt {i + 1}</span>
              <span className="text-xs text-muted-foreground">
                {s.delivered_at ? "livré" : "à livrer"}
                {s.payment_collected ? " · payé" : ""}
              </span>
            </div>
            <div className="text-sm">
              {s.order?.location?.landmark_text} — {s.order?.location?.commune}
            </div>
            <div className="text-sm text-muted-foreground">
              {s.order?.customer_phone} · {s.order?.quantity_liters} L ·{" "}
              {Number(s.order?.total_price_dzd ?? 0).toLocaleString()} DZD
            </div>
            <div className="mt-1 flex gap-2">
              <Button
                size="sm"
                disabled={!!s.delivered_at || delivered.isPending}
                onClick={() => delivered.mutate(s.id)}
              >
                Marquer livré
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={
                  !s.delivered_at || s.payment_collected || paid.isPending
                }
                onClick={() => paid.mutate(s.id)}
              >
                Cash encaissé
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
