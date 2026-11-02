import { Fragment, useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, Collapse, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton, Paper, Stack, Switch,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import HistoryIcon from "@mui/icons-material/History";
import LockIcon from "@mui/icons-material/Lock";
import DeleteIcon from "@mui/icons-material/DeleteOutline";
import { tariffsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { STAGE } from "@/components/Stage";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { useAppSelector } from "@/store";
import type { TariffHist, TariffOverview } from "@/types";
import type { RefData } from "./AdminHome";
import { fmtMoney } from "./CompaniesTab";

const todayIso = () => new Date(Date.now() + 5 * 3600_000).toISOString().slice(0, 10);
type Target = { region_id?: number; district_id?: number; name: string; current: number | null };

/** Ta'riflar (1 m³, QQS bilan): viloyat → tuman/shahar. Admin — hammasi va qulf; manager — o'z tumanlari (qulflanmagan bo'lsa). */
export function TariffsTab(_: RefData) {
  const { t, tErr } = useI18n();
  const isAdmin = useAppSelector((s) => s.auth.user?.role) === "admin";
  const [data, setData] = useState<TariffOverview | null>(null);
  const [edit, setEdit] = useState<Target | null>(null);
  const [hist, setHist] = useState<string | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const load = useCallback(() => tariffsApi.overview().then(setData).catch(fail), [fail]);
  useEffect(() => { load(); }, [load]);
  const lock = async (body: { region_id?: number; district_id?: number; locked: boolean }) => {
    try { await tariffsApi.lock(body); toast(t(body.locked ? "tf_locked_ok" : "tf_unlocked_ok")); load(); } catch (e) { fail(e); }
  };
  const remove = async (h: TariffHist) => {
    try { await tariffsApi.remove(h.id); toast(t("tf_removed")); load(); } catch (e) { fail(e); }
  };
  const History = ({ id, rows }: { id: string; rows: TariffHist[] }) => (
    <Collapse in={hist === id} unmountOnExit>
      <Table size="small" sx={{ my: 1 }}>
        <TableHead><TableRow><TableCell>{t("tf_from")}</TableCell><TableCell align="right">{t("tf_price")}</TableCell><TableCell>{t("tf_note")}</TableCell>
          <TableCell>{t("tf_by")}</TableCell><TableCell /></TableRow></TableHead>
        <TableBody>{rows.map((h) => <TableRow key={h.id} data-hist={h.id}>
          <TableCell>{h.valid_from}</TableCell><TableCell align="right">{fmtMoney(h.price)}</TableCell><TableCell>{h.note ?? ""}</TableCell>
          <TableCell>{h.by ?? "—"}</TableCell>
          <TableCell>{h.valid_from > (data?.today ?? "") && <IconButton size="small" onClick={() => remove(h)} aria-label={t("delete")}><DeleteIcon fontSize="small" /></IconButton>}</TableCell>
        </TableRow>)}
          {!rows.length && <TableRow><TableCell colSpan={5}><Typography variant="caption" color="text.secondary">—</Typography></TableCell></TableRow>}
        </TableBody>
      </Table>
    </Collapse>
  );

  return (
    <Stack spacing={2} id="tariffs">
      <Alert severity="info" variant="outlined">{t(isAdmin ? "tf_hint_admin" : "tf_hint_manager")}</Alert>
      {data?.regions.map((r) => (
        <Paper key={r.region_id} variant="outlined" sx={{ p: 2 }} data-region={r.name}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" fontWeight={700}>{r.name}</Typography>
              <Typography variant="body2">{t("tf_region_price")}: <b data-region-price>{r.price != null ? fmtMoney(r.price) : t("tf_none")}</b>
                {r.upcoming && <Chip size="small" sx={{ ml: 1 }} label={t("tf_upcoming", { p: fmtMoney(r.upcoming.price), d: r.upcoming.valid_from })} />}</Typography>
            </Box>
            {r.locked && !isAdmin && <Chip icon={<LockIcon />} label={t("tf_locked")} color="warning" size="small" />}
            {isAdmin && <FormControlLabel control={<Switch checked={r.locked} onChange={(e) => lock({ region_id: r.region_id, locked: e.target.checked })}
              data-lock-region={r.region_id} />} label={t("tf_lock_region")} />}
            <Button size="small" startIcon={<HistoryIcon />} onClick={() => setHist(hist === `r${r.region_id}` ? null : `r${r.region_id}`)}>{t("tf_history")}</Button>
            {r.can_edit && <Button size="small" variant="contained" disableElevation startIcon={<EditIcon />} data-edit-region={r.region_id}
              onClick={() => setEdit({ region_id: r.region_id, name: r.name, current: r.price })}>{t("tf_change")}</Button>}
          </Stack>
          <History id={`r${r.region_id}`} rows={r.history} />
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead><TableRow><TableCell>{t("district")}</TableCell><TableCell align="right">{t("tf_current")}</TableCell>
              <TableCell>{t("tf_source")}</TableCell><TableCell>{t("tf_next")}</TableCell>{isAdmin && <TableCell>{t("tf_manager_lock")}</TableCell>}<TableCell /></TableRow></TableHead>
            <TableBody>
              {r.districts.map((d) => <Fragment key={d.district_id}>
                <TableRow hover data-district={d.name}>
                  <TableCell>{d.name}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, whiteSpace: "nowrap" }} data-price>{d.price != null ? fmtMoney(d.price) : "—"}</TableCell>
                  <TableCell>{d.own_price != null ? <Chip size="small" label={t("tf_own")} sx={{ bgcolor: STAGE.green.bg, color: "#fff" }} />
                    : <Typography variant="caption" color="text.secondary">{t("tf_from_region")}</Typography>}</TableCell>
                  <TableCell>{d.upcoming ? t("tf_upcoming", { p: fmtMoney(d.upcoming.price), d: d.upcoming.valid_from }) : "—"}</TableCell>
                  {isAdmin && <TableCell><Switch size="small" checked={d.locked} data-lock-district={d.district_id}
                    onChange={(e) => lock({ district_id: d.district_id, locked: e.target.checked })} /></TableCell>}
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    <IconButton size="small" onClick={() => setHist(hist === `d${d.district_id}` ? null : `d${d.district_id}`)} aria-label={t("tf_history")}><HistoryIcon fontSize="small" /></IconButton>
                    {d.can_edit ? <Button size="small" startIcon={<EditIcon />} data-edit-district={d.district_id}
                      onClick={() => setEdit({ district_id: d.district_id, name: d.name, current: d.price })}>{t("tf_change")}</Button>
                      : <Tooltip title={t("tf_locked_hint")}><LockIcon fontSize="small" color="disabled" sx={{ verticalAlign: "middle" }} /></Tooltip>}
                  </TableCell>
                </TableRow>
                {hist === `d${d.district_id}` && <TableRow><TableCell colSpan={isAdmin ? 6 : 5}><History id={`d${d.district_id}`} rows={d.history} /></TableCell></TableRow>}
              </Fragment>)}
            </TableBody>
          </Table>
        </Paper>
      ))}
      {edit && <TariffDialog target={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} fail={fail} />}
    </Stack>
  );
}

function TariffDialog({ target, onClose, onSaved, fail }: { target: Target; onClose: () => void; onSaved: () => void; fail: (e: unknown) => void }) {
  const { t } = useI18n();
  const [price, setPrice] = useState(target.current ? String(target.current) : "");
  const [from, setFrom] = useState(todayIso());
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await tariffsApi.set({ region_id: target.region_id, district_id: target.district_id, price: Number(price), valid_from: from, note: note.trim() || null });
      toast(t("tf_saved"), "success");
      onSaved();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs" id="tariff-dialog">
      <DialogTitle>{t("tf_change")}: {target.name}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary">{t("tf_current")}: {target.current != null ? fmtMoney(target.current) : "—"}</Typography>
          <TextField name="tariff_price" type="number" label={t("tf_new_price")} value={price} onChange={(e) => setPrice(e.target.value)} autoFocus
            helperText={t("tf_vat_incl")} />
          <TextField name="tariff_from" type="date" label={t("tf_from")} value={from} onChange={(e) => setFrom(e.target.value)} InputLabelProps={{ shrink: true }}
            helperText={t("tf_from_hint")} />
          <TextField name="tariff_note" label={t("tf_note")} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("tf_note_ph")} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("cancel")}</Button>
        <Button id="tariff-save" variant="contained" disableElevation disabled={busy || !(Number(price) > 0) || !from} onClick={save}>{t("save")}</Button>
      </DialogActions>
    </Dialog>
  );
}
