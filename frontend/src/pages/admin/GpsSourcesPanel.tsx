import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, MenuItem, Paper, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/EditOutlined";
import HistoryIcon from "@mui/icons-material/History";
import LinkIcon from "@mui/icons-material/Link";
import SyncIcon from "@mui/icons-material/Sync";
import { dispatchApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import type { District, GpsSlot, GpsSourceRow, GpsSourcesOverview, GpsSyncLogRow, GpsTokenStatus } from "@/types";

const when = (iso: string | null) => (iso ? new Date(iso + "Z").toLocaleString("ru-RU", { timeZone: "Asia/Tashkent" }).slice(0, 17) : "—");
const TOKEN_COLOR: Record<GpsTokenStatus, "default" | "warning" | "success" | "error"> = { none: "default", pending: "warning", ok: "success", invalid: "error" };
type Form = { id?: number; system: string; server: string; account: string; backup_account: string; district_id: number | ""; unit_group: string };
const EMPTY: Form = { system: "smartgps", server: "", account: "", backup_account: "", district_id: "", unit_group: "" };

/** Har ulanishda ikki token: asosiy va zaxira (boshqa akkauntdan bo'lishi mumkin). Worker har soatda tekshiradi, o'lsa o'zi zaxiraga
 *  o'tadi va adminlarga bildirishnoma yuboradi (qo'ng'iroqchadagi «Ulash» shu panelga olib keladi). */
/** Admin: SmartGPS/Wialon ulanishlari (PR-B). «Ulash» — SmartGPS'ning o'z kirish sahifasi (parol CRM'ga kelmaydi), token faqat
 *  o'qish huquqli va bazada shifrlangan. Tekshiruv va sinxronlash — gps-worker (30 soniya ichida). */
export function GpsSourcesPanel({ districts }: { districts: District[] }) {
  const { t, tErr } = useI18n();
  const [data, setData] = useState<GpsSourcesOverview | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [paste, setPaste] = useState<{ id: number; slot: GpsSlot; token: string } | null>(null);
  const [log, setLog] = useState<{ src: GpsSourceRow; rows: GpsSyncLogRow[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const load = useCallback(() => dispatchApi.sources().then(setData).catch(fail), [fail]);
  useEffect(() => { load(); }, [load]);
  const waiting = !!data?.sources.some((s) => s.token_status === "pending" || s.backup_token_status === "pending" || s.sync_requested);
  useEffect(() => {  // qo'ng'iroqchadagi «Ulash» → /admin#geozones: panelga aylantiriladi
    if (data && window.location.hash === "#geozones") document.getElementById("gps-sources")?.scrollIntoView({ block: "start" });
  }, [!!data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!waiting) return;
    const h = window.setInterval(load, 5000);
    return () => window.clearInterval(h);
  }, [waiting, load]);

  const save = async () => {
    if (!form) return;
    setBusy(true);
    try {
      const body = { district_id: form.district_id === "" ? null : form.district_id, unit_group: form.unit_group.trim() || null };
      const backup_account = form.backup_account.trim() || null;
      if (form.id) await dispatchApi.updateSource(form.id, { ...body, account: form.account.trim(), backup_account });
      else {
        const { id } = await dispatchApi.createSource({ ...body, system: form.system, server: form.server.trim(), account: form.account.trim() });
        if (backup_account) await dispatchApi.updateSource(id, { backup_account });
      }
      setForm(null);
      await load();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const connect = async (s: GpsSourceRow, slot: GpsSlot = "main") => {
    try {
      const url = await dispatchApi.connectUrl(s.id, `${window.location.origin}/admin/gps-callback/${s.id}${slot === "backup" ? "/backup" : ""}`);
      window.location.assign(url);
    } catch (e) { fail(e); }
  };
  const savePasted = async () => {
    if (!paste) return;
    setBusy(true);
    try { await dispatchApi.setToken(paste.id, paste.token.trim(), paste.slot); setPaste(null); toast(t("gpsc_token_saved"), "success"); await load(); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); await load(); } catch (e) { fail(e); } };
  const w = data?.worker;

  return (
    <Paper variant="outlined" sx={{ p: 2 }} id="gps-sources">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ mb: 1 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ flex: 1 }}>{t("gpsc_title")}</Typography>
        {w && <Chip size="small" id="gps-worker" variant="outlined" color={!w.enabled ? "default" : w.alive ? "success" : "error"}
          label={!w.enabled ? t("gpsc_worker_off") : w.alive ? t("gpsc_worker_alive") : t("gpsc_worker_dead", { t: when(w.seen_at) })} />}
        <Button size="small" startIcon={<AddIcon />} onClick={() => setForm({ ...EMPTY })}>{t("gpsc_add")}</Button>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{t("gpsc_hint")}</Typography>
      {data && !data.encryption_ready && <Alert severity="warning" sx={{ mb: 1 }}>{t("gpsc_no_key")}</Alert>}
      {data?.sources.filter((s) => s.is_active && s.alert_state !== "ok").map((s) =>
        <Alert key={s.id} severity={s.alert_state === "down" ? "error" : "warning"} sx={{ mb: 1 }} data-alert={s.id}
          action={<Button color="inherit" size="small" startIcon={<LinkIcon />} onClick={() => connect(s, s.alert_state === "d:backup" ? "backup" : "main")}>
            {t("gpsc_connect")}</Button>}>
          {t(s.alert_state === "down" ? "gpsc_alert_down" : "gpsc_alert_dead", { server: s.server })}</Alert>)}
      <TableContainer><Table size="small">
        <TableHead><TableRow><TableCell>{t("gpsc_server")}</TableCell><TableCell>{t("district")}</TableCell>
          <TableCell>{t("gpsc_unit_group")}</TableCell><TableCell>{t("gpsc_token")}</TableCell><TableCell>{t("gpsc_last_sync")}</TableCell>
          <TableCell align="right" /></TableRow></TableHead>
        <TableBody>
          {data?.sources.map((s) => <TableRow key={s.id} data-source={s.id} sx={{ verticalAlign: "top", opacity: s.is_active ? 1 : 0.5 }}>
            <TableCell><b>{s.server}</b><Typography variant="caption" display="block" color="text.secondary">{s.system} · {s.account}</Typography></TableCell>
            <TableCell>{s.district ?? "—"}</TableCell>
            <TableCell>{s.unit_group ?? <Typography variant="caption" color="text.secondary">{t("gpsc_all_units")}</Typography>}</TableCell>
            <TableCell sx={{ minWidth: 230 }}>
              {(["main", "backup"] as const).map((slot) => {
                const st = slot === "main" ? s.token_status : s.backup_token_status;
                const user = slot === "main" ? s.token_user : s.backup_token_user;
                const at = slot === "main" ? s.token_set_at : s.backup_token_set_at;
                return <Box key={slot} data-slot={slot} sx={{ mb: 0.75 }}>
                  <Stack direction="row" spacing={0.75} alignItems="center">
                    <Typography variant="caption" sx={{ width: 52 }}>{t(slot === "main" ? "gpsc_main" : "gpsc_backup")}</Typography>
                    <Chip size="small" color={TOKEN_COLOR[st]} label={t(`gpsc_tok_${st}`)} />
                    {st === "ok" && s.active_slot === slot && <Chip size="small" variant="outlined" color="success" label={t("gpsc_active")} />}
                  </Stack>
                  {user && <Typography variant="caption" display="block" color="text.secondary" sx={{ pl: "58px" }}>{user} · {when(at)}</Typography>}
                </Box>;
              })}
              {s.token_checked_at && <Typography variant="caption" display="block" color="text.secondary">{t("gpsc_checked", { t: when(s.token_checked_at) })}</Typography>}
              {s.token_status !== "none" && s.backup_token_status === "none" &&
                <Typography variant="caption" display="block" color="warning.main">{t("gpsc_no_backup")}</Typography>}
            </TableCell>
            <TableCell sx={{ maxWidth: 320 }}>
              <Typography variant="body2">{s.sync_requested ? t("gpsc_sync_queued") : when(s.last_sync_at)}</Typography>
              {s.last_stats && <Typography variant="caption" display="block" color="text.secondary">
                {t("gpsc_stats", { z: s.zones, n: s.last_stats.zones_new, c: s.last_stats.zones_changed, d: s.last_stats.zones_deactivated,
                  g: s.groups, v: s.vehicles_linked })}</Typography>}
              {s.last_error && <Typography variant="caption" display="block" color="error">{s.last_error}</Typography>}
            </TableCell>
            <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
              <Button size="small" variant={s.token_status === "ok" ? "text" : "contained"} disableElevation startIcon={<LinkIcon />}
                onClick={() => connect(s)} disabled={!data.encryption_ready}>{t("gpsc_connect")}</Button>
              <Button size="small" variant={s.backup_token_status === "invalid" ? "contained" : "text"} color={s.backup_token_status === "invalid" ? "warning" : "primary"}
                disableElevation startIcon={<LinkIcon />} onClick={() => connect(s, "backup")} disabled={!data.encryption_ready} data-connect="backup">
                {t("gpsc_connect_backup")}</Button>
              <Tooltip title={t("gpsc_sync_now")}><span><IconButton size="small" disabled={s.token_status === "none" || s.sync_requested}
                onClick={() => act(() => dispatchApi.sync(s.id))}><SyncIcon fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title={t("gpsc_log")}><IconButton size="small" onClick={() => dispatchApi.log(s.id).then((rows) => setLog({ src: s, rows })).catch(fail)}>
                <HistoryIcon fontSize="small" /></IconButton></Tooltip>
              <Tooltip title={t("edit")}><IconButton size="small" onClick={() => setForm({ id: s.id, system: s.system, server: s.server, account: s.account,
                backup_account: s.backup_account ?? "", district_id: s.district_id ?? "", unit_group: s.unit_group ?? "" })}><EditIcon fontSize="small" /></IconButton></Tooltip>
              <Box>
                <Button size="small" onClick={() => setPaste({ id: s.id, slot: "main", token: "" })} disabled={!data.encryption_ready}>{t("gpsc_paste")}</Button>
                <Button size="small" onClick={() => setPaste({ id: s.id, slot: "backup", token: "" })} disabled={!data.encryption_ready}>{t("gpsc_paste_backup")}</Button>
                {s.token_status !== "none" && <Button size="small" color="error" onClick={() => act(() => dispatchApi.clearToken(s.id))}>
                  {t("gpsc_disconnect")} ({t("gpsc_main")})</Button>}
                {s.backup_token_status !== "none" && <Button size="small" color="error" onClick={() => act(() => dispatchApi.clearToken(s.id, "backup"))}>
                  {t("gpsc_disconnect")} ({t("gpsc_backup")})</Button>}
                <Button size="small" onClick={() => act(() => dispatchApi.updateSource(s.id, { is_active: !s.is_active }))}>
                  {s.is_active ? t("gpsc_pause") : t("gpsc_resume")}</Button>
              </Box>
            </TableCell>
          </TableRow>)}
          {data && !data.sources.length && <TableRow><TableCell colSpan={6}><Typography color="text.secondary">{t("gpsc_empty")}</Typography></TableCell></TableRow>}
        </TableBody>
      </Table></TableContainer>

      <Dialog open={!!form} onClose={() => setForm(null)} fullWidth maxWidth="xs">
        <DialogTitle>{form?.id ? t("gpsc_edit") : t("gpsc_add")}</DialogTitle>
        {form && <DialogContent><Stack spacing={2} sx={{ mt: 1 }}>
          <TextField select label={t("gpsc_system")} value={form.system} disabled={!!form.id} onChange={(e) => setForm({ ...form, system: e.target.value })}>
            <MenuItem value="smartgps">SmartGPS</MenuItem><MenuItem value="wialon">Wialon</MenuItem></TextField>
          <TextField label={t("gpsc_server")} value={form.server} disabled={!!form.id} placeholder="gps.example.uz" id="gpsc-server"
            onChange={(e) => setForm({ ...form, server: e.target.value })} />
          <TextField label={t("gpsc_account")} value={form.account} helperText={t("gpsc_account_hint")} id="gpsc-account"
            onChange={(e) => setForm({ ...form, account: e.target.value })} />
          <TextField label={t("gpsc_backup_account")} value={form.backup_account} helperText={t("gpsc_backup_account_hint")} id="gpsc-backup-account"
            onChange={(e) => setForm({ ...form, backup_account: e.target.value })} />
          <TextField select label={t("district")} value={form.district_id} onChange={(e) => setForm({ ...form, district_id: e.target.value === "" ? "" : Number(e.target.value) })}>
            <MenuItem value="">—</MenuItem>
            {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}</TextField>
          <TextField label={t("gpsc_unit_group")} value={form.unit_group} helperText={t("gpsc_unit_group_hint")}
            onChange={(e) => setForm({ ...form, unit_group: e.target.value })} />
        </Stack></DialogContent>}
        <DialogActions><Button onClick={() => setForm(null)}>{t("cancel")}</Button>
          <Button variant="contained" disableElevation onClick={save} id="gpsc-save"
            disabled={busy || !form || !form.account.trim() || (!form.id && !form.server.trim())}>{t("save")}</Button></DialogActions>
      </Dialog>

      <Dialog open={!!paste} onClose={() => setPaste(null)} fullWidth maxWidth="sm">
        <DialogTitle>{t(paste?.slot === "backup" ? "gpsc_paste_backup" : "gpsc_paste")}</DialogTitle>
        <DialogContent><Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{t("gpsc_paste_hint")}</Typography>
          <TextField fullWidth autoComplete="off" label={t("gpsc_token")} value={paste?.token ?? ""} inputProps={{ spellCheck: false }}
            onChange={(e) => paste && setPaste({ ...paste, token: e.target.value })} /></DialogContent>
        <DialogActions><Button onClick={() => setPaste(null)}>{t("cancel")}</Button>
          <Button variant="contained" disableElevation onClick={savePasted} disabled={busy || !paste?.token.trim()}>{t("save")}</Button></DialogActions>
      </Dialog>

      <Dialog open={!!log} onClose={() => setLog(null)} fullWidth maxWidth="md">
        <DialogTitle>{t("gpsc_log")} — {log?.src.server}</DialogTitle>
        <DialogContent><Table size="small">
          <TableHead><TableRow><TableCell>{t("gpsc_started")}</TableCell><TableCell>{t("gpsc_result")}</TableCell></TableRow></TableHead>
          <TableBody>{log?.rows.map((r) => <TableRow key={r.id}><TableCell sx={{ whiteSpace: "nowrap" }}>{when(r.started_at)}</TableCell>
            <TableCell>{r.ok && r.stats
              ? t("gpsc_stats", { z: r.stats.zones, n: r.stats.zones_new, c: r.stats.zones_changed, d: r.stats.zones_deactivated, g: r.stats.groups,
                v: r.stats.vehicles_linked })
              : <Typography variant="body2" color="error">{r.error}</Typography>}</TableCell></TableRow>)}
            {log && !log.rows.length && <TableRow><TableCell colSpan={2}>{t("gpsc_log_empty")}</TableCell></TableRow>}</TableBody>
        </Table></DialogContent>
        <DialogActions><Button onClick={() => setLog(null)}>{t("close")}</Button></DialogActions>
      </Dialog>
    </Paper>
  );
}
