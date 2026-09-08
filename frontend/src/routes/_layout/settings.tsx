import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  {
    value: "my-profile",
    titleKey: "settings.tabProfile",
    component: UserInformation,
  },
  {
    value: "danger-zone",
    titleKey: "settings.tabDanger",
    component: DeleteAccount,
  },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
})

function UserSettings() {
  const { t } = useTranslation()
  const { user: currentUser } = useAuth()

  if (!currentUser) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("settings.title")}
        </h1>
        <p className="text-muted-foreground">{t("settings.subtitle")}</p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {tabsConfig.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {t(tab.titleKey)}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabsConfig.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
