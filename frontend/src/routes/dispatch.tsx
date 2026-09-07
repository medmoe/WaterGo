import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useCallback, useState } from "react"

import {
  DispatchService,
  FleetService,
  OrdersService,
  UsersService,
} from "@/client"
import { PointsMap } from "@/components/Map/maps"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isLoggedIn } from "@/hooks/useAuth"
import { useLiveChannel } from "@/hooks/useLiveChannel"

export const Route = createFileRoute("/dispatch")({
  component: Dispatch,
  beforeLoad: async () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" })
    const { data: me } = await UsersService.readUserMe()
    if (me.role !== "dispatcher" && me.role !== "admin") {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({ meta: [{ title: "Dispatch" }] }),
})

function Dispatch() {
  const qc = useQueryClient()
  const invalidateAll = useCallback(() => {
    qc.invalidateQueries()
  }, [qc])
  useLiveChannel("/ws/dispatch", invalidateAll)

  const pending = useQuery({
    queryKey: ["orders", "pending"],
    refetchInterval: 20000,
    queryFn: async () =>
      (await OrdersService.listOrders({ query: { status: "pending" } })).data,
  })
  const map = useQuery({
    queryKey: ["dispatch", "pending-map"],
    refetchInterval: 20000,
    queryFn: async () => (await DispatchService.pendingMap()).data,
  })
  const routes = useQuery({
    queryKey: ["dispatch", "routes"],
    refetchInterval: 20000,
    queryFn: async () => (await DispatchService.listRoutes()).data,
  })
  const vehicles = useQuery({
    queryKey: ["vehicles"],
    queryFn: async () => (await FleetService.listVehicles()).data,
  })
  const drivers = useQuery({
    queryKey: ["users", "drivers"],
    queryFn: async () =>
      (await UsersService.readUsers({ query: { limit: 200 } })).data,
  })

  const confirm = useMutation({
    mutationFn: (id: string) =>
      OrdersService.confirmOrder({ path: { order_id: id } }),
    onSuccess: invalidateAll,
  })

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [vehicleId, setVehicleId] = useState("")
  const [driverId, setDriverId] = useState("")
  const [plannedDate, setPlannedDate] = useState(
    new Date().toISOString().slice(0, 10),
  )
  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })

  const createRoute = useMutation({
    mutationFn: () =>
      DispatchService.createRoute({
        body: {
          vehicle_id: vehicleId,
          driver_id: driverId,
          planned_date: plannedDate,
          order_ids: [...selected],
        },
      }),
    onSuccess: () => {
      setSelected(new Set())
      invalidateAll()
    },
  })

  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      DispatchService.updateRoute({
        path: { route_id: id },
        body: { status: status as never },
      }),
    onSuccess: invalidateAll,
  })

  const driverList = (drivers.data?.data ?? []).filter(
    (u) => u.role === "driver",
  )

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-8 flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Tableau de dispatch</h1>

      <Tabs defaultValue="confirm">
        <TabsList>
          <TabsTrigger value="confirm">
            À confirmer ({pending.data?.count ?? 0})
          </TabsTrigger>
          <TabsTrigger value="build">Carte &amp; tournées</TabsTrigger>
          <TabsTrigger value="routes">Tournées</TabsTrigger>
          <TabsTrigger value="fleet">Flotte</TabsTrigger>
        </TabsList>

        <TabsContent value="confirm" className="flex flex-col gap-3">
          {(pending.data?.data ?? []).map((o) => (
            <Card key={o.id}>
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <div className="text-sm">
                  <div className="font-medium">{o.customer_phone}</div>
                  <div className="text-muted-foreground">
                    {o.quantity_liters} L · {o.location?.landmark_text} ·{" "}
                    {o.location?.commune}
                  </div>
                </div>
                <Button
                  size="sm"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate(o.id)}
                >
                  Confirmer
                </Button>
              </CardContent>
            </Card>
          ))}
          {pending.data?.count === 0 && (
            <p className="text-muted-foreground text-sm">
              Aucune commande en attente.
            </p>
          )}
        </TabsContent>

        <TabsContent value="build" className="flex flex-col gap-4">
          <PointsMap
            className="h-72 w-full overflow-hidden rounded-md border"
            points={(map.data ?? []).map((p) => ({
              id: p.order_id,
              lat: p.raw_lat,
              lng: p.raw_lng,
              label: `${p.customer_phone} — ${p.quantity_liters} L`,
              onClick: () => toggle(p.order_id),
            }))}
          />
          <Card>
            <CardHeader>
              <CardTitle>Nouvelle tournée ({selected.size} arrêts)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="max-h-48 overflow-auto flex flex-col gap-2">
                {(map.data ?? []).map((p) => (
                  <div
                    key={p.order_id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <Checkbox
                      id={`stop-${p.order_id}`}
                      checked={selected.has(p.order_id)}
                      onCheckedChange={() => toggle(p.order_id)}
                    />
                    <label htmlFor={`stop-${p.order_id}`}>
                      {p.customer_phone} · {p.quantity_liters} L · {p.commune}
                    </label>
                  </div>
                ))}
                {map.data?.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    Aucune commande confirmée sans tournée.
                  </p>
                )}
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="grid gap-1">
                  <Label>Camion</Label>
                  <select
                    className="h-9 rounded-md border bg-background px-2 text-sm"
                    value={vehicleId}
                    onChange={(e) => setVehicleId(e.target.value)}
                  >
                    <option value="">—</option>
                    {(vehicles.data?.data ?? []).map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.plate_number} ({v.capacity_liters} L)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-1">
                  <Label>Chauffeur</Label>
                  <select
                    className="h-9 rounded-md border bg-background px-2 text-sm"
                    value={driverId}
                    onChange={(e) => setDriverId(e.target.value)}
                  >
                    <option value="">—</option>
                    {driverList.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.full_name || d.phone_number}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-1">
                  <Label>Date</Label>
                  <Input
                    type="date"
                    value={plannedDate}
                    onChange={(e) => setPlannedDate(e.target.value)}
                  />
                </div>
              </div>
              {createRoute.isError && (
                <p className="text-sm text-destructive">
                  Impossible de créer la tournée (vérifiez le chauffeur et les
                  commandes).
                </p>
              )}
              <Button
                disabled={
                  createRoute.isPending ||
                  !vehicleId ||
                  !driverId ||
                  selected.size === 0
                }
                onClick={() => createRoute.mutate()}
              >
                Créer la tournée
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="routes" className="flex flex-col gap-3">
          {(routes.data?.data ?? []).map((r) => (
            <Card key={r.id}>
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <div className="text-sm">
                  <div className="font-medium">
                    {r.planned_date} · {(r.stops ?? []).length} arrêts ·{" "}
                    {r.status}
                  </div>
                  <div className="text-muted-foreground">
                    {(r.stops ?? [])
                      .map((s) => s.order?.location?.commune)
                      .filter(Boolean)
                      .join(", ")}
                  </div>
                </div>
                <div className="flex gap-2">
                  {r.status === "planned" && (
                    <Button
                      size="sm"
                      onClick={() =>
                        advance.mutate({ id: r.id, status: "in_progress" })
                      }
                    >
                      Démarrer
                    </Button>
                  )}
                  {r.status === "in_progress" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        advance.mutate({ id: r.id, status: "completed" })
                      }
                    >
                      Terminer
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="fleet" className="flex flex-col gap-3">
          <NewVehicle onDone={invalidateAll} />
          {(vehicles.data?.data ?? []).map((v) => (
            <Card key={v.id}>
              <CardContent className="flex items-center justify-between py-4 text-sm">
                <span className="font-medium">{v.plate_number}</span>
                <span className="text-muted-foreground">
                  {v.capacity_liters} L · {v.status} · {v.current_odometer_km}{" "}
                  km
                </span>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function NewVehicle({ onDone }: { onDone: () => void }) {
  const [plate, setPlate] = useState("")
  const [capacity, setCapacity] = useState(3000)
  const m = useMutation({
    mutationFn: () =>
      FleetService.createVehicle({
        body: { plate_number: plate, capacity_liters: capacity },
      }),
    onSuccess: () => {
      setPlate("")
      onDone()
    },
  })
  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-3 py-4">
        <div className="grid gap-1">
          <Label>Plaque</Label>
          <Input value={plate} onChange={(e) => setPlate(e.target.value)} />
        </div>
        <div className="grid gap-1">
          <Label>Capacité (L)</Label>
          <Input
            type="number"
            value={capacity}
            onChange={(e) => setCapacity(Number(e.target.value) || 0)}
          />
        </div>
        <Button disabled={!plate || m.isPending} onClick={() => m.mutate()}>
          Ajouter
        </Button>
      </CardContent>
    </Card>
  )
}
