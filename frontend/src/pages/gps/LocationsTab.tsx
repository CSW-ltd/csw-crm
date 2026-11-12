/** GPS: joylashuvni tasdiqlash — legal shartnomada kiritgan (yoki kiritmagan) nuqta/geofence/kadastr.
 * Faqat «Tasdiqlash» va «O'zgartirish» (legal kiritganini o'zgartirsa — izoh majburiy; legal'ga bildirishnoma ketadi). */
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import { locationsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import type { Geofence, LocationQueueItem } from "@/types";
import type { MapValue } from "@/components/MapEditor";

const MapEditor = lazy(() => import("@/components/MapEditor"));

export function LocationsTab({ onCount }: { onCount?: (n: number) => void }) {
  const { t } = useI18n();
  const [items, setItems] = useState<LocationQueueItem[] | null>(null);
  const [open, setOpen] = useState<LocationQueueItem | null>(null);
  const load = useCallback(async () => {
    const r = await locationsApi.queue();
    setItems(r); onCount?.(r.length);
  }, [onCount]);
  useEffect(() => { load().catch(() => setItems([])); }, [load]);
  if (!items) return <Typography color="text.secondary">…</Typography>;
  return (
    <Stack spacing={1.5} id="gps-locations">
      {!items.length && <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>{t("loc_empty")}</Typography>}
      {items.map((x) => (
        <Box key={x.customer.id} data-location={x.customer.id} onClick={() => setOpen(x)} sx={{ cursor: "pointer", border: 1, borderColor: "divider",
          borderLeft: 6, borderLeftColor: x.state === "missing" ? "error.main" : "warning.main", borderRadius: 1, p: 1.5, "&:hover": { bgcolor: "action.hover" } }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography fontWeight={700}>{x.contract?.number ?? "—"}</Typography>
            <Typography>· {x.customer.name}</Typography>
            <Chip size="small" color={x.state === "missing" ? "error" : "warning"} label={t(`loc_state_${x.state}`)} />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {[x.customer.legal_address, x.customer.cadastre && `${t("loc_kadastr")}: ${x.customer.cadastre}`,
              x.entered_by && t("loc_entered_by", { name: x.entered_by })].filter(Boolean).join(" · ")}
          </Typography>
        </Box>
      ))}
      {open && <ConfirmDialog item={open} onClose={() => setOpen(null)} onDone={() => { setOpen(null); load().catch(() => undefined); }} />}
    </Stack>
  );
}

function ConfirmDialog({ item, onClose, onDone }: { item: LocationQueueItem; onClose: () => void; onDone: () => void }) {
  const { t, tErr } = useI18n();
  const c = item.customer;
  const orig: MapValue = { lat: c.lat, lng: c.lng, geofence: c.geofence };
  const [val, setVal] = useState<MapValue>(orig);
  const [cad, setCad] = useState(c.cadastre ?? "");
  const [editing, setEditing] = useState(item.state === "missing");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const fromLegal = item.state === "pending" && c.location_source === "legal";
  const ready = val.lat != null && val.lng != null && !!val.geofence;
  const save = async () => {
    if (!ready) { toast(t("loc_need_geofence"), "error"); return; }
    setBusy(true);
    try {
      await locationsApi.confirm(c.id, { lat: val.lat!, lng: val.lng!, geofence: val.geofence as Geofence, cadastre: cad.trim() || null,
        comment: comment.trim() || null });
      toast(t("loc_confirmed_ok"), "success"); onDone();
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); } finally { setBusy(false); }
  };
  return (
    <Dialog open onClose={() => !busy && onClose()} fullWidth maxWidth="md" id="loc-dialog">
      <DialogTitle sx={{ fontWeight: 700 }}>{item.contract?.number ?? "—"} · {c.name}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary">
            {[c.legal_address, item.entered_by && t("loc_entered_by", { name: item.entered_by })].filter(Boolean).join(" · ")}
          </Typography>
          {item.state === "missing" && <Alert severity="warning">{t("loc_state_missing")}</Alert>}
          <Suspense fallback={<Typography color="text.secondary">…</Typography>}>
            <MapEditor value={val} onChange={editing ? setVal : undefined} height={420} />
          </Suspense>
          {!val.geofence && <Alert severity="info">{t("loc_need_geofence")}</Alert>}
          <TextField size="small" label={t("loc_kadastr")} value={cad} onChange={(e) => setCad(e.target.value)} disabled={!editing}
            inputProps={{ maxLength: 40 }} />
          {editing && fromLegal && <TextField id="loc-comment" size="small" multiline minRows={2} label={t("loc_comment")} value={comment}
            onChange={(e) => setComment(e.target.value)} inputProps={{ maxLength: 500 }} />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 1.5, gap: 1 }}>
        <Button onClick={onClose} disabled={busy}>{t("cancel")}</Button>
        {!editing && <Button id="loc-change" variant="outlined" onClick={() => setEditing(true)} disabled={busy}>{t("loc_change")}</Button>}
        <Button id="loc-confirm" variant="contained" disableElevation onClick={save} disabled={busy || !ready}>
          {t(editing && fromLegal ? "loc_save_change" : "loc_confirm")}</Button>
      </DialogActions>
    </Dialog>
  );
}
