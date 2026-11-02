import { useCallback, useEffect, useState } from "react";
import { Accordion, AccordionDetails, AccordionSummary, Box, Button, Chip, FormControlLabel, MenuItem, Paper, Stack, Switch, Table,
  TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ErrorIcon from "@mui/icons-material/ErrorOutline";
import InfoIcon from "@mui/icons-material/InfoOutlined";
import WarningIcon from "@mui/icons-material/WarningAmber";
import CheckIcon from "@mui/icons-material/CheckCircleOutline";
import { adminApi, situationApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { SITUATION_EVENT, useSituation, useSituationText } from "@/components/Situation";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { clearSessionAlerts, onSessionAlert, sessionAlerts, toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import type { SituationEvent, SituationLevel } from "@/types";
import { districtLabel, type RefData } from "./AdminHome";
import { useAppSelector } from "@/store";
import { saveBlob } from "./ContractWizard";
import DownloadIcon from "@mui/icons-material/Download";
import HistoryIcon from "@mui/icons-material/History";

/** Tuman xodimlari faoliyati jurnali (backend: situation.activity) */
export const ACTIVITY_KINDS = ["act_request_created", "act_request_cancelled", "act_assigned", "act_form_printed",
  "act_print_confirmed", "act_form_closed", "act_act_completed", "act_contract_started", "act_contract_saved", "act_contract_signed",
  "act_contract_imported", "act_contract_import", "act_contract_approved", "act_contract_returned", "act_tariff_set", "act_tariff_lock",
  "act_payment", "act_payment_cancelled", "act_payment_import", "act_invoices_generated", "act_invoices_sent"] as const;

export const SITUATION_KINDS = ["account_locked", "act_suspect", "request_failed", "location_pending", "import_done", "user_created",
  "user_deactivated", "user_activated", "password_reset", "district_deactivated", "district_activated", "vehicle_deactivated",
  "vehicle_activated", "settings_changed", "staff_pending", "staff_approved", "staff_rejected", "staff_updated", "access_changed",
  "vehicle_created", "vehicle_updated", "customer_created", "customer_updated", "district_radius_changed", "request_overdue", "order_locked", "order_reprint",
  "request_reassigned"] as const;

const LEVEL_ICON = {
  info: <InfoIcon color="info" fontSize="small" />, activity: <HistoryIcon color="action" fontSize="small" />, warning: <WarningIcon color="warning" fontSize="small" />,
  error: <ErrorIcon color="error" fontSize="small" />, success: <CheckIcon color="success" fontSize="small" />,
};

function useSessionAlerts() {
  const [list, setList] = useState(() => [...sessionAlerts()]);
  useEffect(() => onSessionAlert(() => setList([...sessionAlerts()])), []);
  return list;
}

/** Vaziyat paneli: serverdagi hodisalar (90 kun) + shu sessiyada ekranda chiqqan xabarlar. */
export function SituationTab({ districts }: RefData) {
  const isAdmin = useAppSelector((st) => st.auth.user?.role) === "admin";
  const { t, tErr } = useI18n();
  const text = useSituationText();
  const ctx = useSituation();
  const session = useSessionAlerts();
  const [items, setItems] = useState<SituationEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [lastRead, setLastRead] = useState(0);
  const [level, setLevel] = useState<SituationLevel | "">("");
  const [kind, setKind] = useState("");
  const [district, setDistrict] = useState<number | "">("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState(25);

  const load = useCallback(async () => {
    try {
      const res = await situationApi.list({ level: level || undefined, kind: kind || undefined, district_id: district || undefined,
        date_from: from || undefined, date_to: to || undefined, unread: onlyUnread || undefined, limit: rows, offset: page * rows });
      setItems(res.items);
      setTotal(res.total);
      setLastRead(res.last_read_id);
      ctx?.setUnread(res.unread);
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
    // ctx.setUnread barqaror (useState setter)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [level, kind, district, from, to, onlyUnread, page, rows, tErr]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const onNew = () => load();
    window.addEventListener(SITUATION_EVENT, onNew);
    return () => window.removeEventListener(SITUATION_EVENT, onNew);
  }, [load]);

  // Manager qo'shgan xodim: admin shu yerdan tasdiqlaydi yoki rad etadi
  const decide = async (userId: number, approve: boolean) => {
    try { await (approve ? adminApi.approveUser(userId) : adminApi.rejectUser(userId)); toast(t("saved")); load(); }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
  };

  const markAll = async () => {
    try { const r = await situationApi.markRead(); ctx?.setUnread(r.unread); setLastRead(r.last_read_id); if (onlyUnread) load(); }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
  };
  const reset = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(0); };
  // Jurnal: tur tanlangan — shu tur PDF; aks holda ZIP (har tur alohida PDF). Filtrlar (daraja, tuman, sana) qo'llanadi.
  const [exporting, setExporting] = useState(false);
  const doExport = async () => {
    setExporting(true);
    try {
      const blob = await situationApi.exportFile({ kind: kind || undefined, level: level || undefined, district_id: district || undefined,
        date_from: from || undefined, date_to: to || undefined });
      saveBlob(blob, kind ? `vaziyat_${kind}.pdf` : "vaziyat_jurnal.zip");
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); } finally { setExporting(false); }
  };

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2 }} alignItems={{ md: "center" }} useFlexGap flexWrap="wrap">
          <TextField id="s-level" size="small" select label={t("sit_level")} value={level} sx={{ minWidth: 150 }}
            onChange={(e) => reset(setLevel)(e.target.value as SituationLevel | "")}>
            <MenuItem value="">{t("all")}</MenuItem>
            {(["error", "warning", "info", "activity"] as const).map((l) => <MenuItem key={l} value={l}>{t(`lvl_${l}`)}</MenuItem>)}
          </TextField>
          <TextField id="s-kind" size="small" select label={t("sit_kind")} value={kind} sx={{ minWidth: 220 }}
            onChange={(e) => reset(setKind)(e.target.value)}>
            <MenuItem value="">{t("all")}</MenuItem>
            {[...ACTIVITY_KINDS, ...SITUATION_KINDS].map((k) => <MenuItem key={k} value={k}>{t(`k_${k}` as MessageKey)}</MenuItem>)}
          </TextField>
          <TextField id="s-district" size="small" select label={t("district")} value={district} sx={{ minWidth: 180 }}
            onChange={(e) => reset(setDistrict)(e.target.value === "" ? "" : Number(e.target.value))}>
            <MenuItem value="">{t("all")}</MenuItem>
            {districts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
          </TextField>
          <TextField id="s-from" size="small" type="date" label={t("date_from")} value={from} InputLabelProps={{ shrink: true }}
            onChange={(e) => reset(setFrom)(e.target.value)} />
          <TextField id="s-to" size="small" type="date" label={t("date_to")} value={to} InputLabelProps={{ shrink: true }}
            onChange={(e) => reset(setTo)(e.target.value)} />
          <FormControlLabel control={<Switch id="s-unread" checked={onlyUnread} onChange={(e) => reset(setOnlyUnread)(e.target.checked)} />}
            label={t("only_unread")} />
          <Button id="s-export" variant="contained" disableElevation startIcon={<DownloadIcon />} sx={{ whiteSpace: "nowrap" }} disabled={exporting}
            onClick={doExport}>{t(kind ? "sit_export_pdf" : "sit_export_zip")}</Button>
          <Button variant="outlined" sx={{ ml: { md: "auto" }, whiteSpace: "nowrap" }} disabled={!ctx?.unread} onClick={markAll}>
            {t("mark_all_read")}{ctx?.unread ? ` (${ctx.unread})` : ""}
          </Button>
        </Stack>

        <TableContainer>
          <Table size="small">
            <TableHead><TableRow>
              <TableCell width={36} /><TableCell sx={{ whiteSpace: "nowrap" }}>{t("date")}</TableCell><TableCell>{t("sit_event")}</TableCell>
              <TableCell>{t("district")}</TableCell><TableCell>{t("sit_actor")}</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {items.map((ev) => {
                const isNew = ev.id > lastRead && ev.level !== "activity";
                return (
                  <TableRow key={ev.id} data-unread={isNew || undefined}
                    sx={{ bgcolor: isNew ? "action.hover" : undefined, "& td:first-of-type": { borderLeft: 3, borderLeftColor: isNew ? `${ev.level}.main` : "transparent" } }}>
                    <TableCell>{LEVEL_ICON[ev.level]}</TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{formatDateTime(new Date(ev.created_at + "Z"))}</TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={isNew ? 600 : 400}>{text(ev)}</Typography>
                      <Typography variant="caption" color="text.secondary">{t(`k_${ev.kind}` as MessageKey)}</Typography>
                      {ev.kind === "staff_pending" && ev.ref_id && !ev.resolved && isAdmin && <Stack direction="row" spacing={1} sx={{ mt: 0.75 }}>
                        <Button size="small" variant="contained" disableElevation onClick={() => decide(ev.ref_id!, true)}>{t("approve")}</Button>
                        <Button size="small" color="error" onClick={() => decide(ev.ref_id!, false)}>{t("reject")}</Button>
                      </Stack>}
                    </TableCell>
                    <TableCell>{ev.district_id ? districtLabel(districts, ev.district_id) : "—"}</TableCell>
                    <TableCell>{ev.actor_name ?? t("sit_system")}</TableCell>
                  </TableRow>
                );
              })}
              {!items.length && <TableRow><TableCell colSpan={5} align="center" sx={{ color: "text.secondary", py: 4 }}>{t("sit_empty")}</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination component="div" count={total} page={page} rowsPerPage={rows} rowsPerPageOptions={[25, 50, 100]}
          onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setRows(Number(e.target.value)); setPage(0); }}
          labelRowsPerPage="" labelDisplayedRows={({ from: a, to: b, count }) => `${a}–${b} / ${count}`} />
        <Typography variant="caption" color="text.secondary">{t("sit_retention")}</Typography>
      </Paper>

      <Accordion variant="outlined" disableGutters defaultExpanded={session.length > 0}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography fontWeight={600}>{t("sit_session")}</Typography>
          <Chip size="small" label={session.length} sx={{ ml: 1 }} />
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{t("sit_session_hint")}</Typography>
          {session.length > 0 ? <>
            <Table size="small"><TableBody>
              {session.map((a) => <TableRow key={a.id}>
                <TableCell width={36}>{LEVEL_ICON[a.icon]}</TableCell>
                <TableCell sx={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{formatDateTime(a.at)}</TableCell>
                <TableCell>{a.title}</TableCell>
              </TableRow>)}
            </TableBody></Table>
            <Box sx={{ mt: 1 }}><Button size="small" onClick={clearSessionAlerts}>{t("clear")}</Button></Box>
          </> : <Typography color="text.secondary">—</Typography>}
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}
