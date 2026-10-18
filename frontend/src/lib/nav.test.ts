import { describe, expect, it } from "vitest";
import { safeNext } from "./nav";

describe("safeNext", () => {
  it("пропускает относительные пути", () => {
    expect(safeNext("/documents")).toBe("/documents");
    expect(safeNext("/a?b=1")).toBe("/a?b=1");
  });
  it("сохраняет query/hash и закодированные слеши", () => {
    expect(safeNext("/documents?x=1#y")).toBe("/documents?x=1#y");
    expect(safeNext("/%2F%2Fevil.com")).toBe("/%2F%2Fevil.com");
  });
  it.each(["//evil.com", "https://x", "/\\evil.com", "documents", "", null, "/\t/evil.com", "/\n/evil.com", "/\r/evil.com", "/\t\\evil.com", "/a\\b", "javascript:alert(1)", "/.//evil.com", "/..//evil.com", "/././/evil.com", "/a/../..//evil.com"])("отвергает %s", (v) => {
    expect(safeNext(v)).toBe("/");
  });
});
