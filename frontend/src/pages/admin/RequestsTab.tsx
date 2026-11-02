import { useCallback, useEffect, useState } from "react";
import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Paper, Stack, Switch, Table,
  TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography } from "@mui/material";
import { requestsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { StageChip } from "@/components/Stage";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import { getSocket } from "@/lib/socket";
import { RequestChips, STATUS_COLOR } from "@/pages/operator/OperatorHome";
import { WASTE_TYPES } from "@/pages/operator/OrderFields";
import type { RequestDetail, RequestItem, RequestStatus } from "@/types";
import { districtLabel, type RefData } from "./AdminHome";
import { usePersisted } from "@/hooks/usePersisted";

const STATUSES: RequestStatus[] = ["new", "printing", "assigned", "enroute", "onsite", "done", "suspect", "failed", "cancelled"];
const dt = (s: string | null | undefined) => (s ? formatDateTime(new Date(s + "Z")) : "—");

/** Arizalar ro'yxati (admin — hammasi, manager — o'z tumanlari): filtrlar, "Yangi" belgisi, karta + tarix, bekor qilish. */
export function RequestsTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const [status, setStatus] = useState<RequestStatus | "">("");
  const [district, setDistrict] = usePersisted<number | "">("req.district", "");
  const [waste, setWaste] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [repeat, setRepeat] = useState(false);
  const [overdue, setOverdue] = useState(false);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState(25);
  const [items, setItems] = useState<RequestItem[]>([]);
  const [total, setTotal] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => { const h = window.setTimeout(() => { setQuery(q); setPage(0); }, 300); return () => window.clearTimeout(h); }, [q]);

  const load = useCallback(async () => {
    try {
      const r = await requestsApi.list({ status: status || undefined, district_id: district || undefined, waste_type: waste || undefined,
        date_from: from || undefined, date_to: to || undefined, repeat: repeat || undefined, overdue: overdue || undefined,
        q: query || undefined, limit: rows, offset: page * rows });
      setItems(r.items); setTotal(r.total);
    } catch (e) { fail(e); }
  }, [status, district, waste, from, to, repeat, overdue, query, page, rows, fail]);
  useEffect(() => {
    load();
    const s = getSocket();
    s.on("request:updated", load);
    return () => { s.off("request:updated", load); };
  }, [load]);

  const reset = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(0); };
  const clear = () => { setStatus(""); setDistrict(""); setWaste(""); setFrom(""); setTo(""); setRepeat(false); setOverdue(false); setQ(""); setPage(0); };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2 }} alignItems={{ md: "center" }} useFlexGap flexWrap="wrap">
        <TextField id="rq-q" size="small" label={t("rq_search")} value={q} onChange={(e) => setQ(e.target.value)} sx={{ minWidth: 220 }} />
        <TextField id="rq-status" size="small" select label={t("status")} value={status} sx={{ minWidth: 150 }}
          onChange={(e) => reset(setStatus)(e.target.value as RequestStatus | "")}>
          <MenuItem value="">{t("all")}</MenuItem>
          {STATUSES.map((s) => <MenuItem key={s} value={s}>{t(`s_${s}` as MessageKey)}</MenuItem>)}
        </TextField>
        {districts.length > 1 && <TextField id="rq-district" size="small" select label={t("district")} value={district} sx={{ minWidth: 170 }}
          onChange={(e) => reset(setDistrict)(e.target.value === "" ? "" : Number(e.target.value))}>
          <MenuItem value="">{t("all")}</MenuItem>
          {districts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
        </TextField>}
        <TextField id="rq-waste" size="small" select label={t("waste_type")} value={waste} sx={{ minWidth: 150 }}
          onChange={(e) => reset(setWaste)(e.target.value)}>
          <MenuItem value="">{t("all")}</MenuItem>
          {WASTE_TYPES.map((w) => <MenuItem key={w} value={w}>{t(`wt_${w}` as MessageKey)}</MenuItem>)}
        </TextField>
        <TextField id="rq-from" size="small" type="date" label={t("date_from")} value={from} InputLabelProps={{ shrink: true }}
          onChange={(e) => reset(setFrom)(e.target.value)} />
        <TextField id="rq-to" size="small" type="date" label={t("date_to")} value={to} InputLabelProps={{ shrink: true }}
          onChange={(e) => reset(setTo)(e.target.value)} />
        <FormControlLabel control={<Switch id="rq-repeat" checked={repeat} onChange={(e) => reset(setRepeat)(e.target.checked)} />} label={t("repeat")} />
        <FormControlLabel control={<Switch id="rq-overdue" checked={overdue} onChange={(e) => reset(setOverdue)(e.target.checked)} />} label={t("overdue")} />
        <Button onClick={clear} sx={{ ml: { md: "auto" } }}>{t("rq_clear")}</Button>
      </Stack>

      <TableContainer>
        <Table size="small" id="rq-table">
          <TableHead><TableRow>
            <TableCell>{t("rq_number")}</TableCell><TableCell>{t("rq_customer")}</TableCell><TableCell>{t("district")}</TableCell>
            <TableCell>{t("status")}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{t("created")}</TableCell><TableCell>{t("due_at")}</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {items.map((r) => {
              const isNew = r.seen === false;
              return (
                <TableRow key={r.id} hover data-request={r.number} data-new={isNew || undefined} onClick={() => setOpenId(r.id)}
                  sx={{ cursor: "pointer", bgcolor: isNew ? "action.hover" : undefined,
                    "& td:first-of-type": { borderLeft: 3, borderLeftColor: isNew ? "primary.main" : "transparent" } }}>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    <Typography variant="body2" fontWeight={isNew ? 700 : 500} component="span">{r.number}</Typography>
                    {isNew && <Chip size="small" color="primary" label={t("rq_new_badge")} sx={{ ml: 1, height: 20 }} />}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={isNew ? 600 : 400}>{r.customer.name}
                      {r.customer.code && <Typography component="span" sx={{ ml: 1, fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>{r.customer.code}</Typography>}</Typography>
                    <Stack direction="row" spacing={0.5} sx={{ mt: 0.25 }} flexWrap="wrap" useFlexGap><RequestChips r={r} /></Stack>
                  </TableCell>
                  <TableCell>{districtLabel(districts, r.district_id)}</TableCell>
                  <TableCell><Stack direction="row" spacing={0.5} alignItems="center"><StageChip stage={r.stage} />
                    <Chip size="small" variant="outlined" color={STATUS_COLOR[r.status]} label={t(`s_${r.status}` as MessageKey)} /></Stack></TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{dt(r.created_at)}</TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums", color: r.overdue ? "error.main" : undefined }}>{dt(r.due_at)}</TableCell>
                </TableRow>
              );
            })}
            {!items.length && <TableRow><TableCell colSpan={6} align="center" sx={{ color: "text.secondary", py: 4 }}>{t("rq_empty")}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination component="div" count={total} page={page} rowsPerPage={rows} rowsPerPageOptions={[25, 50, 100]}
        onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setRows(Number(e.target.value)); setPage(0); }}
        labelRowsPerPage="" labelDisplayedRows={({ from: a, to: b, count }) => `${a}–${b} / ${count}`} />
      {openId && <RequestDialog id={openId} districts={districts} onClose={() => setOpenId(null)} onChanged={load} />}
    </Paper>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return <Box><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="body2">{value || "—"}</Typography></Box>;
}

export function RequestDialog({ id, districts, onClose, onChanged }: { id: number; districts: RefData["districts"]; onClose: () => void; onChanged: () => void }) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [d, setD] = useState<RequestDetail | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");

  useEffect(() => { requestsApi.detail(id).then((x) => { setD(x); onChanged(); }).catch((e) => { fail(e); onClose(); }); /* eslint-disable-next-line */ }, [id]);

  const doCancel = async () => {
    setBusy(true);
    try { await requestsApi.cancel(id, reason.trim()); toast(t("rq_cancelled")); onChanged(); onClose(); } catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      {d && <>
        <DialogTitle sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          {d.number} · {d.customer.name}
          <Chip size="small" color={STATUS_COLOR[d.status]} label={t(`s_${d.status}` as MessageKey)} />
          <RequestChips r={d} />
        </DialogTitle>
        <DialogContent dividers id="rq-dialog">
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(3, 1fr)" } }}>
            <Field label={t("district")} value={districtLabel(districts, d.district_id)} />
            <Field label={t("rq_address")} value={d.customer.address} />
            <Field label={t("stir")} value={d.customer.stir} />
            <Field label={t("caller_name")} value={d.caller_name} />
            <Field label={t("caller_phone")} value={d.caller_phone} />
            <Field label={t("rq_source")} value={d.source ? t(`src_${d.source}` as MessageKey) : null} />
            <Field label={t("waste_type")} value={t(`wt_${d.waste_type}` as MessageKey)} />
            <Field label={t("rq_volume")} value={d.volume_estimate} />
            <Field label={t("rq_preferred")} value={d.preferred_time} />
            <Field label={t("created")} value={`${dt(d.created_at)}${d.created_by_name ? ` · ${d.created_by_name}` : ""}`} />
            <Field label={t("due_at")} value={dt(d.due_at)} />
            <Field label={t("rq_finished")} value={dt(d.finished_at)} />
            <Field label={t("rq_driver")} value={d.driver_name} />
            <Field label={t("naryad")} value={d.naryad_no} />
            <Field label={t("cust_code")} value={d.customer.code} />
            <Field label={t("of_no")} value={d.order_form?.number} />
            <Field label={t("vehicle")} value={d.vehicle?.plate} />
            <Field label={t("rq_contract")} value={d.contract?.number} />
          </Box>
          {d.note && <Box sx={{ mt: 1.5 }}><Field label={t("rq_note")} value={d.note} /></Box>}
          {d.cancel_reason && <Typography color="error" sx={{ mt: 1.5 }}>{t("rq_cancel_reason")}: {d.cancel_reason}</Typography>}

          <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>{t("rq_history")}</Typography>
          {!d.events.length && <Typography variant="body2" color="text.secondary">—</Typography>}
          <Box component="ol" id="rq-history" sx={{ listStyle: "none", m: 0, p: 0, borderLeft: 2, borderColor: "divider", ml: 1 }}>
            {d.events.map((e, i) => (
              <Box component="li" key={i} sx={{ position: "relative", pl: 2, pb: 1.5,
                "&::before": { content: '""', position: "absolute", left: -6, top: 6, width: 10, height: 10, borderRadius: "50%",
                  bgcolor: `${STATUS_COLOR[e.status] === "default" ? "grey" : STATUS_COLOR[e.status]}.main` } }}>
                <Typography variant="body2" fontWeight={600}>{t(`s_${e.status}` as MessageKey)}
                  <Typography component="span" variant="caption" color="text.secondary"> · {dt(e.created_at)}{e.actor_name && ` · ${e.actor_name}`}</Typography>
                </Typography>
                {e.note && <Typography variant="body2" color="text.secondary">{e.note}</Typography>}
              </Box>
            ))}
          </Box>

          {cancelling && <TextField id="rq-cancel-reason" fullWidth autoFocus multiline minRows={2} sx={{ mt: 2 }} label={t("rq_cancel_reason")}
            value={reason} onChange={(e) => setReason(e.target.value)} inputProps={{ maxLength: 300 }} />}
        </DialogContent>
        <DialogActions>
          {d.status === "new" && can("requests.cancel") && (cancelling
            ? <>
              <Button onClick={() => setCancelling(false)}>{t("back")}</Button>
              <Button id="rq-cancel-confirm" color="error" variant="contained" disableElevation disabled={busy || reason.trim().length < 3} onClick={doCancel}>
                {t("rq_cancel_do")}</Button>
            </>
            : <Button id="rq-cancel" color="error" onClick={() => setCancelling(true)} sx={{ mr: "auto" }}>{t("rq_cancel")}</Button>)}
          {!cancelling && <><Button onClick={onClose}>{t("close")}</Button></>}
        </DialogActions>
      </>}
    </Dialog>
  );
}
