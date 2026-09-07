import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"

import { OrdersService, PricingService } from "@/client"
import { PinPicker } from "@/components/Map/maps"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"

export const Route = createFileRoute("/")({
  component: OrderForm,
  head: () => ({ meta: [{ title: "Commander de l'eau — Batna" }] }),
})

const MAX_LITERS = 4000

function OrderForm() {
  const navigate = useNavigate()
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null)
  const [landmark, setLandmark] = useState("")
  const [commune, setCommune] = useState("")
  const [liters, setLiters] = useState(1000)
  const [phone, setPhone] = useState("")

  const { data: pricing } = useQuery({
    queryKey: ["pricing", "current"],
    queryFn: async () => (await PricingService.readCurrentPricing()).data,
  })
  const pricePerLiter = pricing ? Number(pricing.price_per_liter_dzd) : 4

  const mutation = useMutation({
    mutationFn: async () => {
      if (!pin) throw new Error("pin required")
      const res = await OrdersService.createOrder({
        body: {
          location: {
            raw_lat: pin.lat,
            raw_lng: pin.lng,
            landmark_text: landmark,
            commune,
          },
          quantity_liters: liters,
          customer_phone: phone,
        },
      })
      return res.data
    },
    onSuccess: (order) => {
      navigate({
        to: "/track/$orderId",
        params: { orderId: order.id },
        search: { phone },
      })
    },
  })

  const valid =
    pin && landmark.trim() && commune.trim() && phone.trim() && liters >= 1

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-8 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Commander une livraison d'eau</h1>
        <p className="text-muted-foreground text-sm">
          Wilaya de Batna · paiement en espèces à la livraison
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Où livrer ?</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <PinPicker
            value={pin}
            onChange={setPin}
            className="h-64 w-full overflow-hidden rounded-md border"
          />
          <p className="text-xs text-muted-foreground">
            {pin
              ? `Point sélectionné : ${pin.lat.toFixed(5)}, ${pin.lng.toFixed(5)}`
              : "Touchez la carte pour placer un repère."}
          </p>
          <div className="grid gap-2">
            <Label>Point de repère</Label>
            <Input
              placeholder="près de la mosquée El Atik"
              value={landmark}
              onChange={(e) => setLandmark(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label>Commune</Label>
            <Input
              placeholder="Batna"
              value={commune}
              onChange={(e) => setCommune(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Votre commande</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label>Quantité (litres) — max {MAX_LITERS}</Label>
            <Input
              type="number"
              min={1}
              max={MAX_LITERS}
              value={liters}
              onChange={(e) =>
                setLiters(
                  Math.max(
                    1,
                    Math.min(MAX_LITERS, Number(e.target.value) || 0),
                  ),
                )
              }
            />
          </div>
          <div className="grid gap-2">
            <Label>Numéro de téléphone</Label>
            <Input
              type="tel"
              placeholder="+2135XXXXXXXX"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div className="rounded-md bg-muted p-3 text-sm">
            {pricePerLiter} DZD / litre ·{" "}
            <span className="font-semibold">
              Total {(pricePerLiter * liters).toLocaleString()} DZD
            </span>
          </div>
          {mutation.isError && (
            <p className="text-sm text-destructive">
              Impossible d'envoyer la commande. Vérifiez les champs et
              réessayez.
            </p>
          )}
          <LoadingButton
            loading={mutation.isPending}
            disabled={!valid}
            onClick={() => mutation.mutate()}
          >
            Envoyer la commande
          </LoadingButton>
        </CardContent>
      </Card>

      <div className="text-center text-sm text-muted-foreground">
        <Link to="/login" className="underline underline-offset-4">
          Espace équipe
        </Link>
      </div>
    </div>
  )
}
