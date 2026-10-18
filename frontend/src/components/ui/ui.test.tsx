import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { ErrorBanner } from "./ErrorBanner";
import { Select } from "./Select";
import { Steps } from "./Steps";
import { Switch } from "./Switch";
import { Tabs } from "./Tabs";
import { TextField } from "./TextField";

describe("Button", () => {
  it("с loading заблокирована и не кликается", async () => {
    const onClick = vi.fn();
    render(<Button variant="primary" loading onClick={onClick}>Запустить</Button>);
    const b = screen.getByRole("button");
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });
  it("обычная кнопка кликается", async () => {
    const onClick = vi.fn();
    render(<Button variant="secondary" onClick={onClick}>Ок</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Ок" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("Tabs", () => {
  it("вызывает onChange и помечает выбранную вкладку", async () => {
    const onChange = vi.fn();
    render(<Tabs items={[{ id: "a", label: "Файл" }, { id: "b", label: "Текст" }]} value="a" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "Файл" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: "Текст" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});

describe("Steps", () => {
  it("помечает текущий шаг aria-current=step", () => {
    render(<Steps steps={["Документ", "Профиль", "Результат"]} current={1} />);
    expect(screen.getByText("Профиль").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Документ").closest("li")).not.toHaveAttribute("aria-current");
  });
});

describe("TextField", () => {
  it("связывает подпись и показывает ошибку", () => {
    render(<TextField label="Email" error="Неверный email" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Неверный email")).toBeInTheDocument();
  });
});

describe("Switch", () => {
  it("переключает", async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Исправлять" />);
    await userEvent.click(screen.getByRole("switch", { name: "Исправлять" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("ErrorBanner", () => {
  it("показывает сообщение с role=alert", () => {
    render(<ErrorBanner message="Нужно войти" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Нужно войти");
  });
});

describe("Select", () => {
  it("вызывает onChange со значением", async () => {
    const onChange = vi.fn();
    render(<Select label="Профиль" options={[{ value: "1", label: "ГОСТ" }, { value: "2", label: "Свой" }]} value="1" onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Профиль"), "2");
    expect(onChange).toHaveBeenCalledWith("2");
  });
});
