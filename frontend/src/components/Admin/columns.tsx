import type { ColumnDef } from "@tanstack/react-table"
import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import i18n from "@/i18n"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "full_name",
    header: i18n.t("admin.colFullName"),
    cell: ({ row }) => {
      const fullName = row.original.full_name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !fullName && "text-muted-foreground")}
          >
            {fullName || "N/A"}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              {i18n.t("admin.you")}
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "phone_number",
    header: i18n.t("admin.colPhone"),
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.phone_number}</span>
    ),
  },
  {
    accessorKey: "role",
    header: i18n.t("admin.colRole"),
    cell: ({ row }) => (
      <Badge variant={row.original.role === "admin" ? "default" : "secondary"}>
        {i18n.t(`roles.${row.original.role ?? "customer"}`)}
      </Badge>
    ),
  },
  {
    accessorKey: "is_active",
    header: i18n.t("admin.colStatus"),
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            row.original.is_active ? "bg-green-500" : "bg-gray-400",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active
            ? i18n.t("admin.active")
            : i18n.t("admin.inactive")}
        </span>
      </div>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">{i18n.t("common.actions")}</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
