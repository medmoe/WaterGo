import { useTranslation } from "react-i18next"

import { Appearance } from "@/components/Common/Appearance"
import { LanguageSwitcher } from "@/components/Common/LanguageSwitcher"

export function PublicTopBar() {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between border-b px-4 py-2">
      <span className="text-sm font-semibold">{t("common.appName")}</span>
      <div className="flex items-center gap-2">
        <LanguageSwitcher />
        <Appearance />
      </div>
    </div>
  )
}
