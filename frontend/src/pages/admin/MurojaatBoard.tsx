import { useCallback, useEffect, useState } from "react";
import { Box, Button, ButtonBase, Chip, InputAdornment, MenuItem, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { useAppSelector } from "@/store";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import PrintIcon from "@mui/icons-material/Print";
import SearchIcon from "@mui/icons-material/Search";
import { ordersApi, requestsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { OrderPaperDialog } from "@/components/OrderPaper";
import { STAGE, useNow } from "@/components/Stage";
import { GreenCard, RedCard, YellowCard } from "@/components/StageCards";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { getSocket } from "@/lib/socket";
import type { RequestItem } from "@/types";
import type { RefData } from "./AdminHome";
import { RequestDialog } from "./RequestsTab";
import { usePersisted } from "@/hooks/usePersisted";

type Color = "red" | "black" | "yellow" | "green";
const COLORS: Color[] = ["red", "black", "yellow", "green"];
const PANEL: Record<Color, { bg: string; fg: string }> = {
  red: { bg: "#d32f2f", fg: "#fff" }, black: { bg: "#141414", fg: "#fff" },
  yellow: { bg: STAGE.yellow.bg, fg: STAGE.yellow.ink }, green: { bg: STAGE.green.bg, fg: "#fff" },
};
const HOURS = [12, 72, 144] as const;

/** Admin (barcha tumanlar) / manager (o'z tumanlari): barcha murojaatlar o'z rangida, 12/72/144 soatlik panellar va rang filtri. */
export function MurojaatBoard({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const now = useNow();
  const [hours, setHours] = usePersisted<(typeof HOURS)[number]>("board.hours", 72);
  const [sum, setSum] = useState<Record<Color, number> | null>(null);
  const [color, setColor] = useState<Color | "">("");
  const role = useAppSelector((st) => st.auth.user?.role);
  const [district, setDistrict] = usePersisted<number | "">("board.district", "");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<RequestItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(60);
  const [open, setOpen] = useState<number | null>(null);
  const [paper, setPaper] = useState<number | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => { const h = window.setTimeout(() => setQuery(q.trim()), 300); return () => window.clearTimeout(h); }, [q]);
  const load = useCallback(async () => {
    try {
      // Soat va tuman filtrlari panellarga ham, ro'yxatga ham birga amal qiladi
      const [s, l] = await Promise.all([requestsApi.summary(hours, district || undefined),
        requestsApi.list({ hours, district_id: district || undefined, stage: color || undefined, q: query || undefined, limit })]);
      setSum(s); setItems(l.items.filter((r) => r.stage !== "cancelled")); setTotal(l.total);
    } catch (e) { fail(e); }
  }, [hours, district, color, query, limit, fail]);
  useEffect(() => {
    load();
    const s = getSocket();
    s.on("request:updated", load);
    return () => { s.off("request:updated", load); };
  }, [load]);

  const act = async (fn: () => Promise<unknown>, msg: string) => { try { await fn(); toast(msg); load(); } catch (e) { fail(e); } };
  const districtName = (id: number) => districts.find((d) => d.id === id)?.name ?? "";

  return (
    <Stack spacing={2} id="board">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} justifyContent="space-between">
        <Typography variant="subtitle1" fontWeight={600}>{t("board_summary", { h: hours })}{district ? ` · ${districts.find((d) => d.id === district)?.name ?? ""}` : ""}</Typography>
        <Stack direction="row" spacing={1.5} alignItems="center">
          {role === "admin" && <TextField id="board-district" select size="small" label={t("district")} value={district} sx={{ minWidth: 200 }}
            onChange={(e) => setDistrict(e.target.value === "" ? "" : Number(e.target.value))}>
            <MenuItem value="">{t("all_districts")}</MenuItem>
            {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
          </TextField>}
          <ToggleButtonGroup size="small" exclusive value={hours} onChange={(_, v) => v && setHours(v)} id="board-hours">
            {HOURS.map((h) => <ToggleButton key={h} value={h} sx={{ px: 2 }}>{t("board_hours", { h })}</ToggleButton>)}
          </ToggleButtonGroup>
        </Stack>
      </Stack>
      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" } }}>
        {COLORS.map((c) => (
          <ButtonBase key={c} data-panel={c} onClick={() => setColor(color === c ? "" : c)} focusRipple
            sx={{ display: "block", textAlign: "left", p: 2, borderRadius: 2, bgcolor: PANEL[c].bg, color: PANEL[c].fg,
              outline: color === c ? "3px solid" : "none", outlineColor: "primary.main", outlineOffset: 2 }}>
            <Typography sx={{ fontSize: 34, fontWeight: 700, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" }} data-count>{sum ? sum[c] : "—"}</Typography>
            <Typography variant="body2" sx={{ opacity: 0.9 }}>{t(`board_${c}`)}</Typography>
          </ButtonBase>
        ))}
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" id="board-filter">
          <Chip clickable label={t("all")} color={!color ? "primary" : "default"} variant={!color ? "filled" : "outlined"} onClick={() => setColor("")} />
          {COLORS.map((c) => <Chip key={c} data-filter={c} clickable onClick={() => setColor(c)} label={t(`board_${c}`)} variant={color === c ? "filled" : "outlined"}
            sx={color === c ? { bgcolor: PANEL[c].bg, color: PANEL[c].fg } : { borderColor: PANEL[c].bg }} />)}
        </Stack>
        <TextField size="small" id="board-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ord_search")} sx={{ ml: { md: "auto" }, minWidth: 300 }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> }} />
      </Stack>

      {!items.length && <Typography color="text.secondary">{t("ord_not_found")}</Typography>}
      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        {items.map((r) => {
          const more = <Button size="small" variant="outlined" color="inherit" onClick={() => setOpen(r.id)}>{t("board_details")}</Button>;
          const f = r.order_form;
          const dname = <Typography variant="caption" sx={{ display: "block", opacity: 0.85, mb: 0.75 }}>{districtName(r.district_id)}</Typography>;
          if (r.stage === "red" || r.stage === "black") {
            return <RedCard key={r.id} r={r} now={now}>{dname}<Stack direction="row" spacing={1} sx={{ "& .MuiButton-root": { color: "#fff", borderColor: "rgba(255,255,255,.6)" } }}>
              {more}</Stack></RedCard>;
          }
          if (r.stage === "yellow") {
            return <YellowCard key={r.id} r={r} now={now}>{dname}<Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {more}
              {f && can("orders.unlock") && f.locked && <Button size="small" color="error" startIcon={<LockOpenIcon />}
                onClick={() => act(() => ordersApi.unlock(f.id), t("of_unlocked"))}>{t("of_unlock")}</Button>}
              {f && can("orders.unlock") && f.printed && !f.reprint_allowed && <Button size="small" data-allow-reprint={r.id} startIcon={<PrintIcon />}
                onClick={() => act(() => ordersApi.allowReprint(f.id), t("of_reprint_ok"))}>{t("of_allow_reprint")}</Button>}
              {f?.reprint_allowed && <Chip size="small" color="warning" label={t("of_reprint_pending")} />}
              {f && <Button size="small" onClick={() => setPaper(f.id)}>{t("of_open")}</Button>}
            </Stack></YellowCard>;
          }
          return <GreenCard key={r.id} r={r}>{dname}<Stack direction="row" spacing={1}>{more}</Stack></GreenCard>;
        })}
      </Box>
      {items.length < total && <Button onClick={() => setLimit((l) => l + 60)}>{t("board_more", { n: total - items.length })}</Button>}
      {open && <RequestDialog id={open} districts={districts} onClose={() => setOpen(null)} onChanged={load} />}
      {paper && <OrderPaperDialog formId={paper} onClose={() => setPaper(null)} onChanged={load} />}
    </Stack>
  );
}
