import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeProvider, useMe } from "./useMe";

afterEach(() => vi.unstubAllGlobals());

function A() {
  const { me, refresh } = useMe();
  return <button onClick={() => void refresh()}>{`a:${me?.email ?? "none"}`}</button>;
}
function B() {
  const { me } = useMe();
  return <p>{`b:${me?.email ?? "none"}`}</p>;
}
const ok = (email: string) => new Response(JSON.stringify({ id: 1, email }), { status: 200 });

describe("MeProvider", () => {
  it("refresh из одного потребителя обновляет другого", async () => {
    const f = vi.fn().mockResolvedValueOnce(new Response("{}", { status: 401 })).mockResolvedValueOnce(ok("x@y.z"));
    vi.stubGlobal("fetch", f);
    render(<MeProvider><A /><B /></MeProvider>);
    await waitFor(() => expect(screen.getByText("b:none")).toBeInTheDocument());
    await act(async () => screen.getByRole("button").click());
    await waitFor(() => expect(screen.getByText("b:x@y.z")).toBeInTheDocument());
  });
  it("500 не разлогинивает", async () => {
    const f = vi.fn().mockResolvedValueOnce(ok("x@y.z")).mockResolvedValueOnce(new Response("{}", { status: 500 }));
    vi.stubGlobal("fetch", f);
    render(<MeProvider><A /><B /></MeProvider>);
    await waitFor(() => expect(screen.getByText("b:x@y.z")).toBeInTheDocument());
    await act(async () => screen.getByRole("button").click());
    expect(f).toHaveBeenCalledTimes(2);
    expect(screen.getByText("b:x@y.z")).toBeInTheDocument();
  });
});
