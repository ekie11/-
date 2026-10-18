"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useMe } from "@/lib/useMe";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();

  useEffect(() => {
    if (!loading && me === null) {
      const here = pathname + (search ? `?${search}` : "");
      router.replace(`/login?next=${encodeURIComponent(here)}`);
    }
  }, [loading, me, router, pathname, search]);

  if (loading || me === null) return null;
  return <>{children}</>;
}
