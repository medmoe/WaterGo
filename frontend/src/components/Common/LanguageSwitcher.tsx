import { Languages } from "lucide-react"
import { useTranslation } from "react-i18next"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SUPPORTED_LANGUAGES } from "@/i18n"

export function LanguageSwitcher({ className }: { className?: string }) {
  const { i18n, t } = useTranslation()
  const current = SUPPORTED_LANGUAGES.includes(
    i18n.language as (typeof SUPPORTED_LANGUAGES)[number],
  )
    ? i18n.language
    : "fr"

  return (
    <Select value={current} onValueChange={(v) => i18n.changeLanguage(v)}>
      <SelectTrigger
        className={className ?? "h-8 w-auto gap-1.5 text-sm"}
        aria-label={t("lang.label")}
      >
        <Languages className="size-4 opacity-70" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {SUPPORTED_LANGUAGES.map((lng) => (
          <SelectItem key={lng} value={lng}>
            {t(`lang.${lng}`)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
