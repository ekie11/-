import { inflateRawSync } from "node:zlib";
import { expect, test } from "@playwright/test";

/** Достаёт запись из zip через центральный каталог (без зависимостей). */
function zipEntry(buf: Buffer, name: string): Buffer {
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("не zip");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    const method = buf.readUInt16LE(p + 10);
    const csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28);
    const elen = buf.readUInt16LE(p + 30);
    const clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const fname = buf.subarray(p + 46, p + 46 + nlen).toString("utf8");
    if (fname === name) {
      const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
      const data = buf.subarray(start, start + csize);
      return method === 0 ? data : inflateRawSync(data);
    }
    p += 46 + nlen + elen + clen;
  }
  throw new Error(`нет записи ${name}`);
}

test("оформление: оглавление становится полем TOC с гиперссылками", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Вставить текст" }).click();
  await page
    .getByLabel("Текст документа")
    .fill("СОДЕРЖАНИЕ\n\nВВЕДЕНИЕ ........ 3\n\n1 Обзор ........ 4\n\nВВЕДЕНИЕ\n\nТекст введения.\n\n1 Обзор\n\nТекст обзора.");
  await page.getByRole("button", { name: "Далее" }).click();
  await expect(page.getByLabel("Требования").locator("option").first()).toBeAttached();
  await page.getByText("Оформить", { exact: true }).click();
  await page.getByRole("button", { name: "Запустить" }).click();

  await expect(page).toHaveURL(/\/jobs\/[\w-]+/);
  const download = page.getByRole("link", { name: "Скачать DOCX" });
  await expect(download).toBeVisible();
  const res = await page.request.get((await download.getAttribute("href"))!);
  expect(res.status()).toBe(200);
  const xml = zipEntry(Buffer.from(await res.body()), "word/document.xml").toString("utf8");
  expect(xml).toContain('TOC \\o "1-3" \\h');
  expect(xml).toMatch(/w:hyperlink w:anchor="_Toc/);
});
