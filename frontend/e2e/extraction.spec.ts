import { expect, test } from "@playwright/test";

test("создание профиля из методички", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`e2e-ex-${Date.now()}@example.com`);
  await page.getByLabel("Пароль").fill("password-123");
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();

  await page.getByRole("link", { name: "Мои профили" }).click();
  await page.getByRole("link", { name: "Создать из методички" }).click();
  await expect(page.getByRole("heading", { name: "Создать из методички" })).toBeVisible();

  await page.getByRole("tab", { name: "Вставить текст" }).click();
  await page.getByLabel("Текст методички").fill("Требования к работе. Поля: левое — 25 мм, правое — 15 мм.");
  await page.getByRole("button", { name: "Извлечь требования" }).click();

  await expect(page.getByRole("cell", { name: "Левое поле", exact: true }).last()).toBeVisible();
  await expect(page.getByRole("cell", { name: "25 мм", exact: true }).first()).toBeVisible();
  await page.getByLabel("Название профиля").fill("Из методички");
  await page.getByRole("button", { name: "Создать профиль" }).click();

  await expect(page).toHaveURL(/\/profiles\/[^/?]+$/);
  await expect(page.getByLabel("Левое поле")).toHaveValue("25");
});
