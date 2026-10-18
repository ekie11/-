import { randomBytes } from "node:crypto";
import { expect, test } from "@playwright/test";

async function upload(request: import("@playwright/test").APIRequestContext, mb: number) {
  return request.post("http://127.0.0.1:3000/api/jobs", {
    multipart: {
      mode: "format",
      file: { name: "x.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: randomBytes(mb * 1024 * 1024) },
    },
  });
}

test("файл ~19 МБ доходит до API через прокси Next", async ({ request }) => {
  const res = await upload(request, 19);
  expect(res.status()).toBeGreaterThanOrEqual(400);
  expect(res.status()).toBeLessThan(500);
  const body = await res.json();
  expect(body.detail).toMatch(/[А-Яа-я]/);
});

test("файл ~22 МБ отклоняется самим API с 413", async ({ request }) => {
  const res = await upload(request, 22);
  expect(res.status()).toBe(413);
});
