import i18n from "@/i18n"

// Algeria uses Latin digits; ar-DZ / fr-DZ keep them Latin (bare "ar" would
// render Arabic-Indic digits, which we don't want for prices).
const localeFor = (lng: string) =>
  lng === "ar" ? "ar-DZ" : lng === "fr" ? "fr-DZ" : "en"

export const fmtNumber = (n: number) =>
  new Intl.NumberFormat(localeFor(i18n.language)).format(n)
