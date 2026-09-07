import { expect, test } from "@playwright/test"

import { randomPhoneNumber } from "./utils/random"

test("customer can place an order and reach the tracking page", async ({
  page,
}) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", { name: /Commander une livraison/i }),
  ).toBeVisible()

  // Drop a pin somewhere on the Batna map.
  const map = page.locator(".leaflet-container")
  await map.waitFor()
  await map.click({ position: { x: 160, y: 120 } })

  await page
    .getByPlaceholder("près de la mosquée El Atik")
    .fill("test landmark")
  await page.getByPlaceholder("Batna").fill("Batna")
  await page.getByPlaceholder("+2135XXXXXXXX").fill(randomPhoneNumber())

  await page.getByRole("button", { name: "Envoyer la commande" }).click()

  await expect(page).toHaveURL(/\/track\//)
  await expect(
    page.getByRole("heading", { name: "Suivi de commande" }),
  ).toBeVisible()
})
