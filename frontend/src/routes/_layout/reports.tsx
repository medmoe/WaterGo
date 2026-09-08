import { useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"

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
import { fmtNumber } from "@/lib/format"

export const Route = createFileRoute("/_layout/reports")({
  component: Reports,
  beforeLoad: async () => {
    const { data: me } = await UsersService.readUserMe()
    if (me.role !== "admin") throw redirect({ to: "/" })
  },
})

function Reports() {
  const { t } = useTranslation()
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
          {t("reports.title")}
        </h1>
        <p className="text-muted-foreground">{t("reports.subtitle")}</p>
      </div>

      <div className="grid w-48 gap-1">
        <Label>{t("reports.date")}</Label>
        <Input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {t("reports.totals", {
              expected: fmtNumber(Number(data?.total_expected_dzd ?? 0)),
              collected: fmtNumber(Number(data?.total_collected_dzd ?? 0)),
            })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.driver")}</TableHead>
                <TableHead>{t("reports.deliveredStops")}</TableHead>
                <TableHead>{t("reports.expected")}</TableHead>
                <TableHead>{t("reports.collectedCount")}</TableHead>
                <TableHead>{t("reports.collected")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.rows ?? []).map((r) => (
                <TableRow key={r.driver_id}>
                  <TableCell>{r.driver_name || r.driver_phone}</TableCell>
                  <TableCell>{r.delivered_stops}</TableCell>
                  <TableCell>
                    {fmtNumber(Number(r.expected_cash_dzd))}
                  </TableCell>
                  <TableCell>{r.collected_stops}</TableCell>
                  <TableCell>
                    {fmtNumber(Number(r.collected_cash_dzd))}
                  </TableCell>
                </TableRow>
              ))}
              {data?.rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">
                    {t("reports.none")}
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
