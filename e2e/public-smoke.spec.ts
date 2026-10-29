import { test, expect } from "@playwright/test";

test("homepage and services pages render and navigation works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("AI-NATIVE DATA REFINERY", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Solution Lab" })).toBeVisible();
  await expect(page.getByText("SOLUTION EXPLORER")).toBeAttached();

  await page.getByRole("button", { name: "Our Services" }).click();
  await expect(page).toHaveURL(/\/our-services$/);
  await expect(page.getByRole("heading", { name: /AI & data solutions/i })).toBeVisible();
  const catalogueLink = page.getByRole("link", { name: /Open Catalogue Data Entry/ });
  await expect(catalogueLink).toBeVisible();
  await catalogueLink.click();
  await expect(page).toHaveURL(/\/our-solutions\/catalogue-data-entry$/);
  await expect(page.getByRole("heading", { name: /Sign in to your catalogue/i })).toBeVisible();
  await expect(page.getByText(/separate from Rivu Data Refinery/i)).toBeVisible();
});
