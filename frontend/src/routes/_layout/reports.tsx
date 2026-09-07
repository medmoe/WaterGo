import { useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useState } from "react"

import { ReportsService, UsersService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export const Route = createFileRoute("/_layout/reports")({
  component: Reports,
  beforeLoad: async () => {
    const { data: me } = await UsersService.readUserMe()
    if (me.role !== "admin") throw redirect({ to: "/" })
  },
  head: () => ({ meta: [{ title: "Rapprochement caisse" }] }),
})

function Reports() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const { data } = useQuery({
    queryKey: ["report", "cash", date],
    queryFn: async () =>
      (await ReportsService.cashReconciliation({ query: { date } })).data,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Rapprochement de caisse
        </h1>
        <p className="text-muted-foreground">
          Cash attendu vs encaissé par chauffeur, arrêts livrés.
        </p>
      </div>

      <div className="grid w-48 gap-1">
        <Label>Date</Label>
        <Input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            Total attendu{" "}
            {Number(data?.total_expected_dzd ?? 0).toLocaleString()} DZD ·
            encaissé {Number(data?.total_collected_dzd ?? 0).toLocaleString()}{" "}
            DZD
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Chauffeur</TableHead>
                <TableHead>Arrêts livrés</TableHead>
                <TableHead>Attendu (DZD)</TableHead>
                <TableHead>Encaissés</TableHead>
                <TableHead>Encaissé (DZD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.rows ?? []).map((r) => (
                <TableRow key={r.driver_id}>
                  <TableCell>{r.driver_name || r.driver_phone}</TableCell>
                  <TableCell>{r.delivered_stops}</TableCell>
                  <TableCell>
                    {Number(r.expected_cash_dzd).toLocaleString()}
                  </TableCell>
                  <TableCell>{r.collected_stops}</TableCell>
                  <TableCell>
                    {Number(r.collected_cash_dzd).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
              {data?.rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    Aucune livraison ce jour-là.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
