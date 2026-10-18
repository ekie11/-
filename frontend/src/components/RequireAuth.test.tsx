import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/profiles",
  useSearchParams: () => new URLSearchParams("x=1"),
}));
const useMe = vi.fn();
vi.mock("@/lib/useMe", () => ({ useMe: () => useMe() }));

import { RequireAuth } from "./RequireAuth";

beforeEach(() => replace.mockReset());

describe("RequireAuth", () => {
  it("гость уходит на /login с next", () => {
    useMe.mockReturnValue({ me: null, loading: false, refresh: vi.fn() });
    render(<RequireAuth>секрет</RequireAuth>);
    expect(replace).toHaveBeenCalledWith("/login?next=" + encodeURIComponent("/profiles?x=1"));
    expect(screen.queryByText("секрет")).toBeNull();
  });
  it("loading — пусто, без перехода", () => {
    useMe.mockReturnValue({ me: null, loading: true, refresh: vi.fn() });
    const { container } = render(<RequireAuth>секрет</RequireAuth>);
    expect(container).toBeEmptyDOMElement();
    expect(replace).not.toHaveBeenCalled();
  });
  it("пользователь видит содержимое", () => {
    useMe.mockReturnValue({ me: { id: 1, email: "a@b.c" }, loading: false, refresh: vi.fn() });
    render(<RequireAuth>секрет</RequireAuth>);
    expect(screen.getByText("секрет")).toBeInTheDocument();
  });
});
