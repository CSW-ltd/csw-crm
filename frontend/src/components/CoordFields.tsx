import { useEffect, useState } from "react";
import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import { useI18n } from "@/i18n/I18nContext";

/** «40.6415, 72.2390», Google Maps (…/@40.64,72.23,17z, ?q=40.64,72.23, !3d40.64!4d72.23) yoki Yandex (?ll=72.23,40.64 — uzunlik birinchi). */
export function parseCoords(text: string): { lat: number; lng: number } | null {
  const s = text.trim();
  if (!s) return null;
  const num = "(-?\\d{1,3}(?:\\.\\d+)?)";
  const pick = (a: string, b: string) => ({ lat: Number(a), lng: Number(b) });
  let m = s.match(new RegExp(`!3d${num}!4d${num}`));
  if (m) return pick(m[1], m[2]);
  m = s.match(new RegExp(`[?&]ll=${num}(?:,|%2C)${num}`, "i"));
  if (m) return pick(m[2], m[1]);  // Yandex: ll=lng,lat
  m = s.match(new RegExp(`@${num},${num}`)) ?? s.match(new RegExp(`[?&](?:q|query|daddr|destination)=${num}(?:,|%2C)\\s*${num}`, "i"));
  if (m) return pick(m[1], m[2]);
  m = s.match(new RegExp(`^${num}\\s*[,;\\s]\\s*${num}$`));
  if (m) return pick(m[1], m[2]);
  return null;
}

const toText = (v: number | null | undefined) => (v == null ? "" : String(v));
const toNum = (s: string) => {
  const n = Number(s.trim().replace(",", "."));
  return s.trim() && Number.isFinite(n) ? n : null;
};

interface Props {
  lat: number | null | undefined;
  lng: number | null | undefined;
  onChange: (lat: number | null, lng: number | null) => void;
  error?: string;
  /** Hozirgi maqom haqida izoh (masalan «tasdiqlangan» / «kutilmoqda») */
  status?: string;
}

/** Obyekt koordinatasi: kenglik + uzunlik, matn/havola joylashtirish va xaritada tekshirish. */
export function CoordFields({ lat, lng, onChange, error, status }: Props) {
  const { t } = useI18n();
  const [la, setLa] = useState(toText(lat));
  const [ln, setLn] = useState(toText(lng));
  const [paste, setPaste] = useState("");
  const [pasteBad, setPasteBad] = useState(false);
  useEffect(() => { if (toNum(la) !== (lat ?? null)) setLa(toText(lat)); }, [lat]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (toNum(ln) !== (lng ?? null)) setLn(toText(lng)); }, [lng]);  // eslint-disable-line react-hooks/exhaustive-deps

  const applyPaste = (text: string) => {
    setPaste(text);
    const c = parseCoords(text);
    setPasteBad(!!text.trim() && !c);
    if (c) { setLa(String(c.lat)); setLn(String(c.lng)); onChange(c.lat, c.lng); }
  };
  const ok = lat != null && lng != null;
  return (
    <Box id="ctr-coords" sx={{ gridColumn: { md: "span 3" } }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "flex-start" }}>
        <TextField size="small" name="coords_paste" label={t("coords_paste")} value={paste} sx={{ flex: 2 }}
          onChange={(e) => applyPaste(e.target.value)} error={pasteBad} helperText={pasteBad ? t("coords_paste_bad") : t("coords_paste_hint")} />
        <TextField size="small" name="coords" label={t("coords_lat")} value={la} required error={!!error} sx={{ flex: 1 }}
          inputProps={{ inputMode: "decimal" }} helperText={error}
          onChange={(e) => { setLa(e.target.value); onChange(toNum(e.target.value), toNum(ln)); }} />
        <TextField size="small" name="coords_lng" label={t("coords_lng")} value={ln} required error={!!error} sx={{ flex: 1 }}
          inputProps={{ inputMode: "decimal" }}
          onChange={(e) => { setLn(e.target.value); onChange(toNum(la), toNum(e.target.value)); }} />
        <Button size="small" startIcon={<MapIcon />} disabled={!ok} sx={{ whiteSpace: "nowrap", mt: { md: 0.5 } }}
          onClick={() => window.open(`https://www.google.com/maps?q=${lat},${lng}`, "_blank", "noopener,noreferrer")}>
          {t("coords_check_map")}</Button>
      </Stack>
      {status && <Typography variant="caption" color="text.secondary" id="ctr-coords-status">{status}</Typography>}
    </Box>
  );
}
