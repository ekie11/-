import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { FieldDef } from "@/lib/fields";
import { ResultTable } from "./ResultTable";

const fields: FieldDef[] = [
  { rule: "page.margins", path: "left_mm", group: "page", label: "Левое поле", kind: "number", unit: "мм" },
  { rule: "page.margins", path: "right_mm", group: "page", label: "Правое поле", kind: "number", unit: "мм" },
];
const base = { "page.margins": { value: { left_mm: 30, right_mm: 15 } } };
const result = {
  found: [
    { rule: "page.margins", path: "left_mm", value: 25, quote: "левое 25", page: 2 },
    { rule: "page.margins", path: "right_mm", value: 15, quote: "правое 15", page: null },
  ],
  unsupported: [{ text: "Рамка на листах", quote: "рамка", page: 3 }],
  rejected_count: 0,
};

function setup(over: Partial<React.ComponentProps<typeof ResultTable>> = {}) {
  const props = {
    result,
    fields,
    groups: [{ id: "page", label: "Страница" }],
    baseRules: base,
    accepted: [0, 1],
    onAccepted: vi.fn(),
    name: "Методичка",
    onName: vi.fn(),
    onCreate: vi.fn(),
    onBack: vi.fn(),
    busy: false,
    ...over,
  };
  render(<ResultTable {...props} />);
  return props;
}

describe("ResultTable", () => {
  it("показывает значения, цитату и приглушает совпадающие с ГОСТом", () => {
    setup();
    expect(screen.getByText("25 мм")).toBeInTheDocument();
    expect(screen.getByText(/левое 25/)).toBeInTheDocument();
    expect(screen.getByText(/стр\. 2/)).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(rows[1]).not.toHaveClass("opacity-50");
    expect(rows[2]).toHaveClass("opacity-50");
  });
  it("«Снять все» и «Выбрать все»", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Снять все" }));
    expect(p.onAccepted).toHaveBeenLastCalledWith([]);
    await userEvent.click(screen.getByRole("button", { name: "Выбрать все" }));
    expect(p.onAccepted).toHaveBeenLastCalledWith([0, 1]);
  });
  it("галочка снимается у одной строки", async () => {
    const p = setup();
    await userEvent.click(screen.getAllByRole("checkbox")[0]);
    expect(p.onAccepted).toHaveBeenLastCalledWith([1]);
  });
  it("блок «не поддерживается» без галочек", () => {
    setup();
    expect(screen.getByText("Найдено, но пока не поддерживается")).toBeInTheDocument();
    expect(screen.getByText("Рамка на листах")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });
  it("создать профиль с названием", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Создать профиль" }));
    expect(p.onCreate).toHaveBeenCalled();
    expect(screen.getByLabelText("Название профиля")).toHaveValue("Методичка");
  });
  it("пустой found", async () => {
    const p = setup({ result: { found: [], unsupported: [], rejected_count: 0 }, accepted: [] });
    expect(screen.getByText("Не нашли требований к оформлению — это точно методичка?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Назад" }));
    expect(p.onBack).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Создать профиль" })).toBeNull();
  });
});

describe("ResultTable: форматы значений", () => {
  it("bool и число", () => {
    const f: FieldDef[] = [
      { rule: "a", path: "b", group: "page", label: "Флаг", kind: "bool" },
      { rule: "a", path: "n", group: "page", label: "Размер", kind: "number", unit: "пт" },
    ];
    render(
      <ResultTable
        result={{ found: [
          { rule: "a", path: "b", value: true, quote: "q", page: null },
          { rule: "a", path: "n", value: 14, quote: "q2", page: null },
        ], unsupported: [], rejected_count: 0 }}
        fields={f} groups={[]} baseRules={{ a: { value: { b: false, n: 12 } } }}
        accepted={[0, 1]} onAccepted={() => {}} name="x" onName={() => {}} onCreate={() => {}} onBack={() => {}} busy={false}
      />,
    );
    expect(screen.getByText("да")).toBeInTheDocument();
    expect(screen.getByText("нет")).toBeInTheDocument();
    expect(screen.getByText("14 пт")).toBeInTheDocument();
    expect(screen.getByText("12 пт")).toBeInTheDocument();
  });
});
