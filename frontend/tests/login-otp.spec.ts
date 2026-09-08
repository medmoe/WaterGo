import { expect, test } from "@playwright/test"

import { randomPhoneNumber } from "./utils/random"

test.beforeEach(async ({ page }) => {
  // Pin the UI language so assertions on visible text are stable.
  await page.addInitScript(() => localStorage.setItem("watergo-lang", "en"))
})

test("OTP login advances from phone step to code step", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible()

  await page.getByTestId("phone-input").fill(randomPhoneNumber())
  await page.getByRole("button", { name: "Send code" }).click()

  // The backend always answers generically, so the UI moves to the code step.
  await expect(page.getByTestId("code-input")).toBeVisible()
  await expect(page.getByRole("button", { name: "Verify" })).toBeVisible()
})

test("language switcher toggles English / Arabic and sets text direction", async ({
  page,
}) => {
  await page.goto("/login")

  const combo = page.getByRole("combobox").first()
  await combo.click()
  await page.getByRole("option", { name: "العربية" }).click()

  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
  await expect(page.locator("html")).toHaveAttribute("lang", "ar")
  await expect(
    page.getByRole("heading", { name: "تسجيل الدخول" }),
  ).toBeVisible()

  await combo.click()
  await page.getByRole("option", { name: "English" }).click()
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr")
})
