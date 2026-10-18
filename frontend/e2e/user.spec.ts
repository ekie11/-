import { expect, test } from "@playwright/test";

test("пользователь: регистрация -> свой профиль -> оформление -> документы", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const profileName = `Профиль ${Date.now()}`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("password-123");
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();

  await page.getByRole("link", { name: "Мои профили" }).click();
  await expect(page.getByRole("heading", { name: "Мои требования" })).toBeVisible();
  await page.getByLabel("Название").fill(profileName);
  await page.getByRole("button", { name: "Создать на основе ГОСТа" }).click();

  await expect(page).toHaveURL(/\/profiles\/[^/?]+/);
  const left = page.getByLabel("Левое поле");
  await left.fill("25");
  await left.blur();
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByRole("button", { name: "Сохранить" })).toBeEnabled();
  await page.reload();
  await expect(page.getByLabel("Левое поле")).toHaveValue("25");

  await page.goto("/");
  await page.getByRole("tab", { name: "Вставить текст" }).click();
  await page.getByLabel("Текст документа").fill("ВВЕДЕНИЕ\n\nТекст работы.");
  await page.getByRole("button", { name: "Далее" }).click();
  await page.getByLabel("Требования").selectOption({ label: profileName });
  await page.getByText("Оформить", { exact: true }).click();
  await page.getByRole("button", { name: "Запустить" }).click();

  await expect(page).toHaveURL(/\/jobs\/[\w-]+/);
  await expect(page.getByRole("link", { name: "Скачать DOCX" })).toBeVisible();

  await page.getByRole("link", { name: "Мои документы" }).click();
  await expect(page.getByRole("cell", { name: profileName })).toBeVisible();
});
