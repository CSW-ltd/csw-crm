import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { MESSAGES, type MessageKey } from "./messages";
import { toCyrillic } from "./translit";

export type Lang = "uz" | "cy" | "ru" | "en";
export const LANGS: { id: Lang; label: string }[] = [
  { id: "uz", label: "O'zbekcha" }, { id: "cy", label: "Ўзбекча" }, { id: "ru", label: "Русский" }, { id: "en", label: "English" },
];

type T = (key: MessageKey, vars?: Record<string, string | number>) => string;
interface I18n { lang: Lang; setLang: (l: Lang) => void; t: T; tErr: (code: string, fallback?: string) => string }

const Ctx = createContext<I18n | null>(null);
const STORAGE_KEY = "csw.lang";

function initialLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY) as Lang | null;
    if (v && LANGS.some((l) => l.id === v)) return v;
  } catch { /* storage yo'q bo'lishi mumkin */ }
  return "uz";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* ignore */ }
  }, []);

  const t = useCallback<T>((key, vars) => {
    // Tarjima topilmasa — sahifa yiqilmasin, kalitning o'zi ko'rsatiladi
    const entry = MESSAGES[key] as readonly [string, string, string] | undefined;
    if (!entry) return String(key);
    const [uz, ru, en] = entry;
    let s: string = lang === "ru" ? ru : lang === "en" ? en : uz;
    if (lang === "cy") s = toCyrillic(s);
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  }, [lang]);

  const tErr = useCallback((code: string, fallback?: string) => {
    const key = `err_${code}` as MessageKey;
    return key in MESSAGES ? t(key) : fallback ?? t("err_unknown");
  }, [t]);

  const value = useMemo(() => ({ lang, setLang, t, tErr }), [lang, setLang, t, tErr]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n I18nProvider ichida ishlatilishi kerak");
  return v;
}
