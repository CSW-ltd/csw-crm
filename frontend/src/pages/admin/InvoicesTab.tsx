import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Box, Tooltip, Button, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, MenuItem, Paper, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import LockIcon from "@mui/icons-material/Lock";
import SendIcon from "@mui/icons-material/Send";
import EventAvailableIcon from "@mui/icons-material/EventAvailable";
import { accountingApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { STAGE } from "@/components/Stage";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { InvoiceItem, MonthForm, MonthFormCustomer } from "@/types";
import type { RefData } from "./AdminHome";
import { fmtM3, fmtMoney } from "./CompaniesTab";
import { UsageBar } from "./ContractsTab";
import { usePersisted } from "@/hooks/usePersisted";

/** "YYYY-MM" — Toshkent vaqti bo'yicha; shift = -1 o'tgan oy */
export const monthIso = (shift = 0) => {
  const d = new Date(Date.now() + 5 * 3600_000);
  const m = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + shift, 1));
  return m.toISOString().slice(0, 7);
};
const asDate = (m: string) => `${m}-01`;
const dmy = (s: string) => s.split("-").reverse().join(".");

function MonthPicker({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  const { t } = useI18n();
  return <TextField id={id} size="small" type="month" label={t("inv_month")} value={value} InputLabelProps={{ shrink: true }}
    onChange={(e) => e.target.value && onChange(e.target.value)} sx={{ width: 180 }} />;
}

async function openPdf(id: number, fail: (e: unknown) => void) {
  const w = window.open("", "_blank");
  try {
    const url = URL.createObjectURL(await accountingApi.invoicePdf(id));
    if (w) w.location.href = url; else window.location.href = url;
  } catch (e) { w?.close(); fail(e); }
}

/** Buxgalteriya «Buyurtma varaqalari»: oy ichida yashil bo'lgan har bir varaqa — summasi amaldagi shartnoma bo'yicha (kub yoki reys). */
export function OrderFormsTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const [month, setMonth] = usePersisted("of.month", monthIso());
  const [district, setDistrict] = useState<number | "">("");
  const [customer, setCustomer] = useState<number | "">("");
  const [data, setData] = useState<{ items: MonthForm[]; customers: MonthFormCustomer[]; total: number; count: number } | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => {
    accountingApi.orderForms(asDate(month), district || undefined).then(setData).catch(fail);
  }, [month, district, fail]);
  const items = useMemo(() => (data?.items ?? []).filter((x) => !customer || x.customer_id === customer), [data, customer]);
  const custs = useMemo(() => (data?.customers ?? []).filter((x) => !customer || x.customer_id === customer), [data, customer]);

  return (
    <Stack spacing={2} id="order-forms">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} useFlexGap flexWrap="wrap">
        <MonthPicker id="of-month" value={month} onChange={(v) => { setMonth(v); setCustomer(""); }} />
        <TextField id="of-district" select size="small" label={t("district")} value={district} sx={{ minWidth: 200 }}
          onChange={(e) => { setDistrict(e.target.value === "" ? "" : Number(e.target.value)); setCustomer(""); }}>
          <MenuItem value="">{t("all_districts")}</MenuItem>
          {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
        </TextField>
        <TextField id="of-customer" select size="small" label={t("cmp_name")} value={customer} sx={{ minWidth: 260 }}
          onChange={(e) => setCustomer(e.target.value === "" ? "" : Number(e.target.value))}>
          <MenuItem value="">{t("inv_all_companies")}</MenuItem>
          {(data?.customers ?? []).map((c) => <MenuItem key={c.customer_id} value={c.customer_id}>{c.name} · {c.code}</MenuItem>)}
        </TextField>
      </Stack>

      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)" } }}>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography sx={{ fontSize: 28, fontWeight: 700 }} data-of-count>{items.length}</Typography>
          <Typography variant="body2" color="text.secondary">{t("inv_forms_count")}</Typography></Paper>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography sx={{ fontSize: 28, fontWeight: 700 }}>{fmtM3(items.reduce((s, x) => s + x.volume_m3, 0))}</Typography>
          <Typography variant="body2" color="text.secondary">{t("cmp_volume")}</Typography></Paper>
        <Paper sx={{ p: 2, bgcolor: STAGE.green.bg, color: "#fff" }} elevation={0}>
          <Typography sx={{ fontSize: 28, fontWeight: 700 }} data-of-total>{fmtMoney(custs.reduce((s, x) => s + x.total, 0))}</Typography>
          <Typography variant="body2">{t("inv_month_total")}</Typography></Paper>
      </Box>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("inv_by_company")}</Typography>
        <TableContainer><Table size="small" id="of-customers">
          <TableHead><TableRow><TableCell>{t("cmp_name")}</TableCell><TableCell>{t("cust_code")}</TableCell><TableCell>{t("district")}</TableCell>
            <TableCell align="right">{t("inv_forms_count")}</TableCell><TableCell>{t("ctr_usage")}</TableCell>
            <TableCell align="right">{t("inv_amount")}</TableCell></TableRow></TableHead>
          <TableBody>
            {custs.map((c) => <TableRow key={c.customer_id} hover data-row={c.code}>
              <TableCell>{c.name}</TableCell><TableCell sx={{ fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>{c.code}</TableCell>
              <TableCell>{districts.find((d) => d.id === c.district_id)?.name}</TableCell>
              <TableCell align="right">{c.forms}{c.pending ? <Chip size="small" label={t("of_pending_n", { n: c.pending })} sx={{ ml: 0.5, height: 18,
                bgcolor: STAGE.yellow.bg, color: STAGE.yellow.ink }} /> : null}</TableCell>
              <TableCell>{c.usage ? <UsageBar c={{ used_m3: c.usage.used, annual_volume: c.usage.annual, usage_pct: c.usage.pct, usage_level: c.usage.level }} />
                : <Typography variant="caption" color="text.secondary">—</Typography>}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>{fmtMoney(c.total)}</TableCell></TableRow>)}
            {!custs.length && <TableRow><TableCell colSpan={6}><Typography color="text.secondary">{t("inv_none")}</Typography></TableCell></TableRow>}
          </TableBody>
        </Table></TableContainer>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("inv_forms_list")}</Typography>
        <TableContainer><Table size="small" id="of-items">
          <TableHead><TableRow>
            <TableCell>{t("date")}</TableCell><TableCell>{t("cmp_name")}</TableCell><TableCell>{t("inv_request")}</TableCell><TableCell>{t("of_no")}</TableCell>
            <TableCell align="right">{t("cmp_volume")}</TableCell><TableCell>{t("inv_contract")}</TableCell>
            <TableCell align="right">{t("inv_price")}</TableCell><TableCell align="right">{t("inv_amount")}</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {items.map((x) => <TableRow key={x.request_id} hover data-form={x.number} data-pending={x.pending || undefined}
              sx={x.pending ? { bgcolor: "#FFFBCC" } : undefined}>
              <TableCell sx={{ whiteSpace: "nowrap" }}>{dmy(x.day)}</TableCell>
              <TableCell>{x.customer_name} <Typography component="span" variant="caption" sx={{ fontFamily: "ui-monospace, monospace" }}>{x.code}</Typography></TableCell>
              <TableCell>{x.number}</TableCell><TableCell sx={{ fontFamily: "ui-monospace, monospace" }}>{x.form_number ?? "—"}</TableCell>
              <TableCell align="right">{fmtM3(x.volume_m3)}</TableCell>
              <TableCell>{x.contract ?? "—"}{x.contract_type && <Typography variant="caption" display="block" color="text.secondary">
                {t(`ct_${x.contract_type}` as MessageKey)}</Typography>}</TableCell>
              <TableCell align="right">{x.price != null && x.contract_type !== "monthly" ? fmtMoney(x.price) : "—"}
                {x.contract_type === "by_volume" && x.price_source === "contract" && <Tooltip title={t("inv_price_contract_hint")}>
                  <Typography variant="caption" display="block" color="text.secondary" data-price-source="contract">{t("inv_price_contract")}</Typography>
                </Tooltip>}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600 }}>{x.pending
                ? <Chip size="small" label={t("of_pending")} sx={{ bgcolor: STAGE.yellow.bg, color: STAGE.yellow.ink, height: 20 }} />
                : x.contract_type === "monthly"
                ? <Typography variant="caption" color="text.secondary">{t("inv_subscriber")}</Typography> : fmtMoney(x.amount)}</TableCell>
            </TableRow>)}
          </TableBody>
        </Table></TableContainer>
        <Typography variant="caption" color="text.secondary">{t("inv_forms_note")}</Typography>
      </Paper>
    </Stack>
  );
}

/** Oylik schyot-fakturalar: oyni yopish (har korxonaga bitta), hammasiga SMS orqali jo'natish, PDF. Yuborilgani qulflanadi. */
export function InvoicesTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [month, setMonth] = usePersisted("inv.month", monthIso(-1));
  const [data, setData] = useState<{ items: InvoiceItem[]; total: number; drafts: number; sent: number } | null>(null);
  const [ask, setAsk] = useState<"generate" | "send" | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const load = useCallback(() => accountingApi.invoices(asDate(month)).then(setData).catch(fail), [month, fail]);
  useEffect(() => { load(); }, [load]);
  const canRun = can("accounting.payments");

  const run = async () => {
    setBusy(true);
    try {
      if (ask === "generate") {
        const r = await accountingApi.generateInvoices(asDate(month));
        toast(t("inv_generated", { c: r.created, u: r.updated, s: r.skipped_sent }), "success");
        if (r.pending_forms) toast(t("inv_pending_warn", { n: r.pending_forms }), "warning");
      } else {
        const r = await accountingApi.sendInvoices(asDate(month));
        toast(t("inv_sent_done", { n: r.sent, p: r.no_phone }), r.no_phone ? "warning" : "success");
      }
      setAsk(null);
      await load();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    <Stack spacing={2} id="invoices">
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }} useFlexGap flexWrap="wrap">
          <MonthPicker id="inv-month" value={month} onChange={setMonth} />
          {data && <Typography data-inv-summary>
            {t("inv_summary", { n: data.items.length, d: data.drafts, s: data.sent })} · <b>{fmtMoney(data.total)}</b></Typography>}
          <Box sx={{ flex: 1 }} />
          {canRun && <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button id="inv-generate" size="large" variant="outlined" startIcon={<EventAvailableIcon />} onClick={() => setAsk("generate")}
              sx={{ borderWidth: 2, "&:hover": { borderWidth: 2 } }}>{t("inv_generate")}</Button>
            <Button id="inv-send" size="large" variant="contained" disableElevation startIcon={<SendIcon />} disabled={!data?.drafts}
              onClick={() => setAsk("send")} sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>
              {t("inv_send_all")}{data?.drafts ? ` (${data.drafts})` : ""}</Button>
          </Stack>}
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>{t("inv_hint")}</Typography>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <TableContainer><Table size="small" id="inv-table">
          <TableHead><TableRow>
            <TableCell>{t("inv_number")}</TableCell><TableCell>{t("cmp_name")}</TableCell><TableCell>{t("district")}</TableCell>
            <TableCell align="right">{t("inv_forms_count")}</TableCell><TableCell align="right">{t("inv_amount")}</TableCell>
            <TableCell align="right">{t("inv_vat")}</TableCell><TableCell>{t("inv_status")}</TableCell><TableCell />
          </TableRow></TableHead>
          <TableBody>
            {data?.items.map((i) => <TableRow key={i.id} hover data-invoice={i.number} data-status={i.status}>
              <TableCell sx={{ fontFamily: "ui-monospace, monospace", whiteSpace: "nowrap" }}>{i.number}</TableCell>
              <TableCell>{i.customer_name} <Typography component="span" variant="caption" sx={{ fontFamily: "ui-monospace, monospace" }}>{i.code}</Typography></TableCell>
              <TableCell>{districts.find((d) => d.id === i.district_id)?.name}</TableCell>
              <TableCell align="right">{i.forms_count}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>{fmtMoney(i.total)}</TableCell>
              <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>{fmtMoney(i.vat)}</TableCell>
              <TableCell>{i.status === "sent"
                ? <Chip size="small" icon={<LockIcon />} label={t("inv_st_sent")} sx={{ bgcolor: STAGE.green.bg, color: "#fff", "& .MuiChip-icon": { color: "#fff" } }} />
                : <Chip size="small" label={t("inv_st_draft")} sx={{ bgcolor: STAGE.yellow.bg, color: STAGE.yellow.ink }} />}
                {i.status === "sent" && !i.sms_phone && <Chip size="small" color="error" variant="outlined" label={t("inv_no_phone")} sx={{ ml: 0.5 }} />}</TableCell>
              <TableCell align="right"><Button size="small" startIcon={<PictureAsPdfIcon />} data-pdf={i.id} onClick={() => openPdf(i.id, fail)}>PDF</Button></TableCell>
            </TableRow>)}
            {data && !data.items.length && <TableRow><TableCell colSpan={8}>
              <Alert severity="info" variant="outlined">{t(canRun ? "inv_empty_run" : "inv_empty")}</Alert></TableCell></TableRow>}
          </TableBody>
        </Table></TableContainer>
      </Paper>

      <Dialog open={!!ask} onClose={() => !busy && setAsk(null)}>
        <DialogTitle>{t(ask === "send" ? "inv_send_all" : "inv_generate")}</DialogTitle>
        <DialogContent><DialogContentText>{t(ask === "send" ? "inv_send_confirm" : "inv_generate_confirm", { m: month.split("-").reverse().join(".") })}</DialogContentText></DialogContent>
        <DialogActions>
          <Button onClick={() => setAsk(null)} disabled={busy}>{t("cancel")}</Button>
          <Button id="inv-confirm" variant="contained" disableElevation onClick={run} disabled={busy}>{t("inv_confirm")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
