import i18n from "i18next"
import LanguageDetector from "i18next-browser-languagedetector"
import { initReactI18next } from "react-i18next"

import ar from "./locales/ar.json"
import en from "./locales/en.json"
import fr from "./locales/fr.json"

export const SUPPORTED_LANGUAGES = ["fr", "en", "ar"] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

export const RTL_LANGUAGES: Language[] = ["ar"]

export function applyDirection(lng: string) {
  const isRtl = RTL_LANGUAGES.includes(lng as Language)
  const root = document.documentElement
  root.setAttribute("lang", lng)
  root.setAttribute("dir", isRtl ? "rtl" : "ltr")
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
      ar: { translation: ar },
    },
    fallbackLng: "fr",
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "watergo-lang",
      caches: ["localStorage"],
    },
  })

applyDirection(i18n.language)
i18n.on("languageChanged", applyDirection)

export default i18n
