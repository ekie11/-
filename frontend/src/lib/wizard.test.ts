import { describe, expect, it } from "vitest";
import { MAX_FILE_BYTES, stepFromQuery, validateFile } from "./wizard";

const file = (name: string, size = 10) => {
  const f = new File(["x"], name);
  Object.defineProperty(f, "size", { value: size });
  return f;
};

describe("validateFile", () => {
  it("отвергает не docx", () => expect(validateFile(file("a.pdf"))).toBe("Нужен файл .docx"));
  it("отвергает большой файл", () =>
    expect(validateFile(file("a.docx", 21 * 1024 * 1024))).toBe("Файл больше 20 МБ"));
  it("принимает docx до 20 МБ, регистр не важен", () => {
    expect(validateFile(file("A.DOCX"))).toBeNull();
    expect(validateFile(file("a.docx", MAX_FILE_BYTES))).toBeNull();
  });
});

describe("stepFromQuery", () => {
  it("шаг 2 только при вводе", () => {
    expect(stepFromQuery("2", true)).toBe(2);
    expect(stepFromQuery("2", false)).toBe(1);
  });
  it("по умолчанию шаг 1", () => {
    expect(stepFromQuery(null, true)).toBe(1);
    expect(stepFromQuery("abc", true)).toBe(1);
  });
});
