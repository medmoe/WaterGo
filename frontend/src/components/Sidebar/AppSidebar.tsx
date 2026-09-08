import { Banknote, MapIcon, Truck, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { LanguageSwitcher } from "@/components/Common/LanguageSwitcher"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

export function AppSidebar() {
  const { t } = useTranslation()
  const { user: currentUser } = useAuth()
  const role = currentUser?.role

  const dispatchItems: Item[] = [
    { icon: MapIcon, title: t("nav.dispatch"), path: "/dispatch" },
  ]
  const driverItems: Item[] = [
    { icon: Truck, title: t("nav.driver"), path: "/driver" },
  ]
  const adminItems: Item[] = [
    { icon: Users, title: t("nav.admin"), path: "/admin" },
    { icon: Banknote, title: t("nav.reports"), path: "/reports" },
  ]

  const items: Item[] = [
    ...(role === "dispatcher" || role === "admin" ? dispatchItems : []),
    ...(role === "driver" || role === "admin" ? driverItems : []),
    ...(role === "admin" ? adminItems : []),
  ]

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <div className="px-2 group-data-[collapsible=icon]:hidden">
          <LanguageSwitcher className="h-8 w-full justify-between text-sm" />
        </div>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
