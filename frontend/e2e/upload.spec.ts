import { randomBytes } from "node:crypto";
import { expect, test } from "@playwright/test";

const MIB = 1024 * 1024;

async function upload(request: import("@playwright/test").APIRequestContext, bytes: number) {
  return request.post("http://127.0.0.1:3000/api/jobs", {
    multipart: {
      mode: "format",
      file: { name: "x.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: randomBytes(bytes) },
    },
  });
}

test("файл ~19 МБ доходит до API через прокси Next", async ({ request }) => {
  const res = await upload(request, 19 * MIB);
  expect(res.status()).toBeGreaterThanOrEqual(400);
  expect(res.status()).toBeLessThan(500);
  expect(res.headers()["content-type"]).toContain("application/json");
  const body = await res.json();
  expect(body.detail).toMatch(/[А-Яа-я]/);
});

test("файл ~22 МБ отклоняется самим API с 413", async ({ request }) => {
  // 21.5 MiB: выше лимита API (21 MiB), но с multipart-обвязкой < 22 MiB, т.е. Next пересылает тело целиком.
  // API отвечает 413 по Content-Length, не дочитав тело, поэтому клиент иногда ловит ECONNRESET на записи: повторяем.
  let res: Awaited<ReturnType<typeof upload>> | undefined;
  for (let attempt = 0; attempt < 5 && !res; attempt++) {
    try {
      res = await upload(request, Math.round(21.5 * MIB));
    } catch (e) {
      if (!String(e).includes("ECONNRESET")) throw e;
    }
  }
  if (!res) throw new Error("ECONNRESET на всех попытках");
  expect(res.status()).toBe(413);
  expect(res.headers()["content-type"]).toContain("application/json");
  const body = await res.json();
  expect(body.detail).toBe("Файл слишком большой — максимум 20 МБ");
});
