import { expect, test } from "@playwright/test"

import { randomPhoneNumber } from "./utils/random"

test("OTP login advances from phone step to code step", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible()

  await page.getByTestId("phone-input").fill(randomPhoneNumber())
  await page.getByRole("button", { name: "Send code" }).click()

  // The backend always answers generically, so the UI moves to the code step.
  await expect(page.getByTestId("code-input")).toBeVisible()
  await expect(page.getByRole("button", { name: "Verify" })).toBeVisible()
})
