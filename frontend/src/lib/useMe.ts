"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch, type Me } from "./api";

export function useMe(): { me: Me | null; loading: boolean; refresh: () => Promise<void> } {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await apiFetch<Me>("/auth/me"));
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  return { me, loading, refresh };
}
