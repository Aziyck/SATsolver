import { useCallback, useState } from "react";

/** useState that remembers its value in localStorage (a per-browser convenience; failures are ignored). */
export function usePersistentState<T>(key: string, initial: () => T): [T, (update: T | ((previous: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) return JSON.parse(stored) as T;
    } catch {
      // storage unavailable or corrupt: fall back to the initial value
    }
    return initial();
  });

  const update = useCallback(
    (next: T | ((previous: T) => T)) => {
      setValue((previous) => {
        const resolved = typeof next === "function" ? (next as (previous: T) => T)(previous) : next;
        try {
          window.localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          // quota exceeded (large CNF text) or storage disabled: keep the in-memory value
        }
        return resolved;
      });
    },
    [key],
  );
  return [value, update];
}
