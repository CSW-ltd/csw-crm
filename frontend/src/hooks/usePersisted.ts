import { useEffect, useState } from "react";

/** Sahifa yangilanganda (refresh) saqlanib qoladigan holat: tab, ichki tab, filtr, tanlangan oy.
 *  Shu brauzer tabining sessionStorage'ida (boshqa tab yoki yangi sessiyaga ta'sir qilmaydi). */
export function usePersisted<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const k = `csw:ui:${key}`;
  const [v, setV] = useState<T>(() => {
    try { const raw = sessionStorage.getItem(k); return raw != null ? (JSON.parse(raw) as T) : initial; } catch { return initial; }
  });
  useEffect(() => {
    try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* xotira yopiq */ }
  }, [k, v]);
  return [v, setV];
}

const LAST = "csw:last-path";
/** Oxirgi ochilgan sahifa (yo'l + #tab): sessiya tugab qayta kirilganda shu yerga qaytiladi. */
export function rememberPath(path: string) {
  if (path === "/" || path.startsWith("/login") || path.startsWith("/change-password")) return;
  try { sessionStorage.setItem(LAST, path); localStorage.setItem(LAST, path); } catch { /* */ }
}
export function lastPath(): string | null {
  try { return sessionStorage.getItem(LAST) ?? localStorage.getItem(LAST); } catch { return null; }
}
