import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge, IconButton } from "@mui/material";
import NotificationsIcon from "@mui/icons-material/Notifications";
import { useNavigate } from "react-router-dom";
import { situationApi } from "@/api/endpoints";
import { useI18n } from "@/i18n/I18nContext";
import { MESSAGES, type MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { getSocket } from "@/lib/socket";
import type { SituationEvent } from "@/types";

interface Ctx { unread: number; setUnread: (n: number) => void; refresh: () => Promise<void> }
const SituationCtx = createContext<Ctx | null>(null);
export const SITUATION_EVENT = "csw:situation";

/** Hodisa matni joriy tilda: `sit_<kind>` kaliti bo'lsa tarjima, bo'lmasa serverdagi o'zbekcha matn. */
export function useSituationText() {
  const { t } = useI18n();
  return useCallback((ev: Pick<SituationEvent, "kind" | "message" | "params">) => {
    const key = `sit_${ev.kind}` as MessageKey;
    if (!(key in MESSAGES)) return ev.message;
    const p: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(ev.params ?? {})) if (v !== null && v !== undefined) p[k] = v as string | number;
    if (typeof p.role === "string" && `r_${p.role}` in MESSAGES) p.role = t(`r_${p.role}` as MessageKey);
    if (typeof p.reason === "string" && `fr_${p.reason}` in MESSAGES) p.reason = t(`fr_${p.reason}` as MessageKey);
    // Ruxsat kodlari ("vehicles.edit") → "Mashinalar: Tahrirlash"
    for (const k of ["added", "removed"]) {
      if (typeof p[k] === "string" && p[k] !== "—") p[k] = (p[k] as string).split(", ").map((code) => {
        const [m, a] = code.split(".");
        return `${t(`m_${m}` as MessageKey)}: ${t((`a_${m}_${a}` in MESSAGES ? `a_${m}_${a}` : `a_${a}`) as MessageKey)}`;
      }).join(", ");
    }
    let s = t(key, p);
    if (ev.kind === "request_failed" && p.note) s += ` — ${p.note}`;
    return s;
  }, [t]);
}

/** Admin va manager uchun: o'qilmaganlar soni va jonli hodisalar (Socket.IO "situation:new"). */
export function SituationProvider({ children }: { children: ReactNode }) {
  const [unread, setUnread] = useState(0);
  const text = useSituationText();
  const refresh = useCallback(async () => {
    try { setUnread((await situationApi.unread()).unread); } catch { /* tarmoq xatosi — keyingi ulanishda qayta olinadi */ }
  }, []);

  useEffect(() => {
    refresh();
    const s = getSocket();
    const onNew = (ev: SituationEvent) => {
      setUnread((n) => n + 1);
      toast(text(ev), ev.level === "error" ? "error" : ev.level === "warning" ? "warning" : "info", { log: false });
      window.dispatchEvent(new CustomEvent(SITUATION_EVENT, { detail: ev }));
    };
    s.on("situation:new", onNew);
    s.on("connect", refresh); // uzilishdan keyin o'tkazib yuborilganlarni hisoblash
    return () => { s.off("situation:new", onNew); s.off("connect", refresh); };
  }, [refresh, text]);

  const value = useMemo(() => ({ unread, setUnread, refresh }), [unread, refresh]);
  return <SituationCtx.Provider value={value}>{children}</SituationCtx.Provider>;
}

export function useSituation(): Ctx | null { return useContext(SituationCtx); }

export function SituationBell() {
  const ctx = useSituation();
  const { t } = useI18n();
  const nav = useNavigate();
  if (!ctx) return null;
  return (
    <IconButton id="situation-bell" aria-label={t("tab_situation")} title={t("tab_situation")} onClick={() => nav("/admin#situation")}>
      <Badge color="error" badgeContent={ctx.unread} max={99}><NotificationsIcon /></Badge>
    </IconButton>
  );
}
