import { expect, test } from "@playwright/test"

import { randomPhoneNumber } from "./utils/random"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("watergo-lang", "en"))
})

test("customer can place an order and reach the tracking page", async ({
  page,
}) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", { name: /Order a water delivery/i }),
  ).toBeVisible()

  // Drop a pin somewhere on the Batna map.
  const map = page.locator(".leaflet-container")
  await map.waitFor()
  await map.click({ position: { x: 160, y: 120 } })

  await page.getByPlaceholder("near the El Atik mosque").fill("test landmark")
  await page.getByPlaceholder("Batna").fill("Batna")
  await page.getByPlaceholder("+2135XXXXXXXX").fill(randomPhoneNumber())

  await page.getByRole("button", { name: "Place the order" }).click()

  await expect(page).toHaveURL(/\/track\//)
  await expect(
    page.getByRole("heading", { name: "Order tracking" }),
  ).toBeVisible()
})
