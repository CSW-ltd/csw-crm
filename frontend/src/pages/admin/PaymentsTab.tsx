import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Autocomplete, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment, Paper, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import UploadIcon from "@mui/icons-material/UploadFile";
import { accountingApi, customersApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import type { CustomerListItem, PaymentImportResult, PaymentItem } from "@/types";
import type { RefData } from "./AdminHome";
import { fmtMoney } from "./CompaniesTab";

const todayIso = () => new Date(Date.now() + 5 * 3600_000).toISOString().slice(0, 10);

/** Buxgalter: to'lovlar — qo'lda kiritish, bekor qilish (o'chirilmaydi), bank ko'chirmasidan import (avval sinov). */
export function PaymentsTab(_: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ items: PaymentItem[]; total: number; sum: number } | null>(null);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [cancelOf, setCancelOf] = useState<PaymentItem | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => { const h = window.setTimeout(() => { setQuery(q.trim()); setPage(0); }, 300); return () => window.clearTimeout(h); }, [q]);
  const load = useCallback(() => accountingApi.payments({ q: query || undefined, date_from: from || undefined, date_to: to || undefined,
    limit: 50, offset: page * 50 }).then(setData).catch(fail), [query, from, to, page, fail]);
  useEffect(() => { load(); }, [load]);

  return (
    <Paper variant="outlined" sx={{ p: 2 }} id="payments">
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }} sx={{ mb: 2 }} useFlexGap flexWrap="wrap">
        <TextField size="small" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("pay_search")} sx={{ minWidth: 260 }} />
        <TextField size="small" type="date" label={t("date_from")} value={from} onChange={(e) => { setFrom(e.target.value); setPage(0); }} InputLabelProps={{ shrink: true }} />
        <TextField size="small" type="date" label={t("date_to")} value={to} onChange={(e) => { setTo(e.target.value); setPage(0); }} InputLabelProps={{ shrink: true }} />
        <Box sx={{ flex: 1 }} />
        {can("accounting.payments") && <>
          <Button id="pay-import" startIcon={<UploadIcon />} onClick={() => setImporting(true)}>{t("pay_import")}</Button>
          <Button id="pay-add" variant="contained" disableElevation startIcon={<AddIcon />} onClick={() => setAdding(true)}>{t("pay_add")}</Button>
        </>}
      </Stack>
      {data && <Typography sx={{ mb: 1 }}>{t("pay_total", { n: data.total })} · <b data-sum>{fmtMoney(data.sum)}</b></Typography>}
      <TableContainer>
        <Table size="small" id="payments-table">
          <TableHead><TableRow>
            <TableCell>{t("date")}</TableCell><TableCell>{t("cmp_name")}</TableCell><TableCell>{t("cust_code")}</TableCell>
            <TableCell align="right">{t("pay_amount")}</TableCell><TableCell>{t("pay_doc")}</TableCell><TableCell>{t("pay_source")}</TableCell><TableCell />
          </TableRow></TableHead>
          <TableBody>
            {data?.items.map((p) => (
              <TableRow key={p.id} data-payment={p.id} sx={p.cancelled ? { opacity: 0.55, "& td": { textDecoration: "line-through" } } : undefined}>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{p.paid_on}</TableCell><TableCell>{p.customer_name}</TableCell>
                <TableCell sx={{ fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>{p.code}</TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{fmtMoney(p.amount)}</TableCell>
                <TableCell>{p.doc_no ?? "—"}</TableCell>
                <TableCell>{t(p.source === "import" ? "pay_src_import" : "pay_src_manual")}</TableCell>
                <TableCell align="right" sx={{ textDecoration: "none !important" }}>
                  {p.cancelled ? <Chip size="small" label={`${t("pay_cancelled")}: ${p.cancel_reason ?? ""}`} />
                    : can("accounting.payments") && <Button size="small" color="error" onClick={() => setCancelOf(p)}>{t("cancel")}</Button>}
                </TableCell>
              </TableRow>
            ))}
            {data && !data.items.length && <TableRow><TableCell colSpan={7} align="center" sx={{ py: 4, color: "text.secondary" }}>{t("pay_empty")}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
      {data && data.total > 50 && <TablePagination component="div" count={data.total} page={page} rowsPerPage={50} rowsPerPageOptions={[50]}
        onPageChange={(_, p) => setPage(p)} labelDisplayedRows={({ from: a, to: b, count }) => `${a}–${b} / ${count}`} />}
      {adding && <AddDialog onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
      {importing && <ImportDialog onClose={() => setImporting(false)} onDone={() => { setImporting(false); load(); }} />}
      {cancelOf && <CancelDialog p={cancelOf} onClose={() => setCancelOf(null)} onDone={() => { setCancelOf(null); load(); }} />}
    </Paper>
  );
}

function AddDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t, tErr } = useI18n();
  const [opts, setOpts] = useState<CustomerListItem[]>([]);
  const [cust, setCust] = useState<CustomerListItem | null>(null);
  const [input, setInput] = useState("");
  const [f, setF] = useState({ paid_on: todayIso(), amount: "", doc_no: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [dup, setDup] = useState(false);  // takror ogohlantirishi: «Baribir saqlash» bilan yoziladi
  useEffect(() => {
    if (input.trim().length < 2) { setOpts([]); return; }
    const h = window.setTimeout(() => customersApi.search({ q: input.trim(), limit: 10 }).then((r) => setOpts(r.items)).catch(() => undefined), 300);
    return () => window.clearTimeout(h);
  }, [input]);
  const amount = Number(f.amount.replace(/\s/g, "").replace(",", "."));
  const save = async (force = false) => {
    if (!cust) return;
    setBusy(true);
    try { await accountingApi.addPayment({ customer_id: cust.id, paid_on: f.paid_on, amount, doc_no: f.doc_no || null, note: f.note || null, force });
      toast(t("saved")); onDone(); }
    catch (e) {
      if (errorCode(e) === "payment_duplicate") setDup(true);
      else toast(tErr(errorCode(e), errorMessage(e)), "error");
    } finally { setBusy(false); }
  };
  const edit = (patch: Partial<typeof f>) => { setF({ ...f, ...patch }); setDup(false); };
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("pay_add")}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Autocomplete id="pay-customer" options={opts} value={cust} onChange={(_, v) => { setCust(v); setDup(false); }} inputValue={input} onInputChange={(_, v) => setInput(v)}
            filterOptions={(x) => x} getOptionLabel={(o) => `${o.code ?? ""} · ${o.name}`} isOptionEqualToValue={(a, b) => a.id === b.id}
            renderInput={(p) => <TextField {...p} label={t("pay_customer")} placeholder="KTR47" />} noOptionsText="—" />
          <Stack direction="row" spacing={1.5}>
            <TextField id="pay-date" type="date" label={t("date")} value={f.paid_on} onChange={(e) => edit({ paid_on: e.target.value })} InputLabelProps={{ shrink: true }} />
            <TextField id="pay-amount" label={t("pay_amount")} value={f.amount} onChange={(e) => edit({ amount: e.target.value.replace(/[^\d\s.,]/g, "") })}
              InputProps={{ endAdornment: <InputAdornment position="end">so'm</InputAdornment> }} sx={{ flex: 1 }} />
          </Stack>
          <TextField id="pay-doc" label={t("pay_doc")} value={f.doc_no} onChange={(e) => edit({ doc_no: e.target.value })} />
          <TextField label={t("rq_note")} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} />
          {dup && <Alert severity="warning" id="pay-dup">{t("pay_dup_warn")}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("cancel")}</Button>
        {dup
          ? <Button id="pay-save-force" variant="contained" color="warning" disableElevation disabled={busy} onClick={() => save(true)}>{t("pay_dup_force")}</Button>
          : <Button id="pay-save" variant="contained" disableElevation disabled={!cust || !(amount > 0) || !f.paid_on || busy} onClick={() => save()}>{t("save")}</Button>}
      </DialogActions>
    </Dialog>
  );
}

function CancelDialog({ p, onClose, onDone }: { p: PaymentItem; onClose: () => void; onDone: () => void }) {
  const { t, tErr } = useI18n();
  const [reason, setReason] = useState("");
  const go = async () => {
    try { await accountingApi.cancelPayment(p.id, reason.trim()); toast(t("saved")); onDone(); }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
  };
  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{t("pay_cancel_title")}</DialogTitle>
      <DialogContent dividers>
        <Typography sx={{ mb: 1.5 }}>{p.customer_name} · {fmtMoney(p.amount)} · {p.paid_on}</Typography>
        <TextField id="pay-cancel-reason" fullWidth autoFocus label={t("rq_cancel_reason")} value={reason} onChange={(e) => setReason(e.target.value)} />
      </DialogContent>
      <DialogActions><Button onClick={onClose}>{t("back")}</Button>
        <Button color="error" variant="contained" disableElevation disabled={reason.trim().length < 3} onClick={go}>{t("pay_cancel_do")}</Button></DialogActions>
    </Dialog>
  );
}

function ImportDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t, tErr } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<PaymentImportResult | null>(null);
  const [include, setInclude] = useState<number[]>([]);  // buxgalter belgilagan ehtimoliy takrorlar
  const [busy, setBusy] = useState(false);
  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    try {
      const r = await accountingApi.importPayments(file, dry, dry ? [] : include);
      if (dry) { setRes(r); setInclude([]); } else { toast(t("pay_imported", { n: r.ok })); onDone(); }
    }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); } finally { setBusy(false); }
  };
  const toWrite = (res?.ok ?? 0) + include.length;
  const toggle = (line: number) => setInclude((xs) => xs.includes(line) ? xs.filter((x) => x !== line) : [...xs, line]);
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t("pay_import")}</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{t("pay_import_hint")}</Typography>
        <input ref={input} id="pay-file" type="file" hidden accept=".xlsx,.xls,.csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setRes(null); setInclude([]); }} />
        <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => input.current?.click()}>{file ? file.name : t("pay_pick_file")}</Button>
        {res && <Box sx={{ mt: 2 }} id="pay-preview">
          <Alert severity={res.errors.length ? "warning" : "success"}>{t("pay_preview", { ok: res.ok, sum: fmtMoney(res.total), err: res.errors.length })}</Alert>
          {res.errors.length > 0 && <Box component="ul" sx={{ m: 0, mt: 1, pl: 3 }}>
            {res.errors.slice(0, 20).map((e) => <li key={e.line}>{t("pay_line", { n: e.line })}: {t(`pay_err_${e.error}` as "pay_err_bad_amount")} ({e.value})</li>)}
          </Box>}
          {res.duplicates > 0 && <Alert severity="info" sx={{ mt: 1 }} id="pay-dups">{t("pay_dups_skipped", { n: res.duplicates })}</Alert>}
          {res.possible.length > 0 && <Box sx={{ mt: 1 }} id="pay-possible">
            <Alert severity="warning">{t("pay_possible_hint", { n: res.possible.length })}</Alert>
            <Table size="small"><TableBody>{res.possible.map((r) => (
              <TableRow key={r.line} data-possible={r.line}>
                <TableCell padding="checkbox"><Checkbox size="small" checked={include.includes(r.line)} onChange={() => toggle(r.line)} /></TableCell>
                <TableCell>{t("pay_line", { n: r.line })}</TableCell><TableCell>{r.paid_on}</TableCell><TableCell>{r.code}</TableCell>
                <TableCell>{r.name}</TableCell><TableCell align="right">{fmtMoney(r.amount)}</TableCell></TableRow>))}</TableBody></Table>
          </Box>}
          <Table size="small" sx={{ mt: 1 }}><TableBody>{res.rows.filter((r) => !r.dup).slice(0, 50).map((r) => (
            <TableRow key={r.line}><TableCell>{r.paid_on}</TableCell><TableCell>{r.code}</TableCell><TableCell>{r.name}</TableCell>
              <TableCell align="right">{fmtMoney(r.amount)}</TableCell><TableCell>{r.doc_no}</TableCell></TableRow>))}</TableBody></Table>
        </Box>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("cancel")}</Button>
        {!res ? <Button id="pay-check" variant="outlined" disabled={!file || busy} onClick={() => run(true)}>{t("pay_check")}</Button>
          : <Button id="pay-commit" variant="contained" disableElevation disabled={!toWrite || busy} onClick={() => run(false)}>{t("pay_commit", { n: toWrite })}</Button>}
      </DialogActions>
    </Dialog>
  );
}
