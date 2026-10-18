import { describe, expect, it } from "vitest";
import { safeNext } from "./nav";

describe("safeNext", () => {
  it("пропускает относительные пути", () => {
    expect(safeNext("/documents")).toBe("/documents");
    expect(safeNext("/a?b=1")).toBe("/a?b=1");
  });
  it.each(["//evil.com", "https://x", "/\\evil.com", "documents", "", null])("отвергает %s", (v) => {
    expect(safeNext(v)).toBe("/");
  });
});
