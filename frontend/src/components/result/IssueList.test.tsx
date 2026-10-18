import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IssueList } from "./IssueList";

describe("IssueList", () => {
  it("показывает русское название правила и источник, не ключ", () => {
    render(<IssueList issues={[{ rule: "body.font_size", source: "ГОСТ 7.32 п. 6.1", message: "Шрифт мал" }]} />);
    expect(screen.getByRole("heading", { name: /Размер шрифта/ })).toHaveTextContent("ГОСТ 7.32 п. 6.1");
    expect(screen.queryByText(/body\.font_size/)).toBeNull();
  });

  it("неизвестный ключ показывается как есть", () => {
    render(<IssueList issues={[{ rule: "custom.rule", source: "", message: "m" }]} />);
    expect(screen.getByRole("heading", { name: "custom.rule" })).toBeInTheDocument();
  });

  it("toc называется «Оглавление»", () => {
    render(<IssueList issues={[{ rule: "toc", source: "", message: "m" }]} />);
    expect(screen.getByRole("heading", { name: "Оглавление" })).toBeInTheDocument();
  });
});
