import { expect, test } from "@playwright/test";

test("гость: текст -> оформление -> сводка -> скачивание DOCX", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Вставить текст" }).click();
  await page.getByLabel("Текст документа").fill("ВВЕДЕНИЕ\n\nТекст работы.");
  await page.getByRole("button", { name: "Далее" }).click();

  const select = page.getByLabel("Требования");
  const gost = select.locator("option", { hasText: "7.32" }).first();
  await expect(gost).toBeAttached();
  await select.selectOption({ label: (await gost.textContent()) ?? "" });
  await page.getByText("Оформить", { exact: true }).click();
  await page.getByRole("button", { name: "Запустить" }).click();

  await expect(page).toHaveURL(/\/jobs\/[\w-]+/);
  await expect(page.getByRole("heading", { name: /Оформление готово/ })).toBeVisible();
  const download = page.getByRole("link", { name: "Скачать DOCX" });
  await expect(download).toBeVisible();

  const res = await page.request.get((await download.getAttribute("href"))!);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toContain("wordprocessingml.document");
});
