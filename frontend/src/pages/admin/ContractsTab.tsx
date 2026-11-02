import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment, LinearProgress, Paper, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import NoteAddIcon from "@mui/icons-material/NoteAdd";
import CheckIcon from "@mui/icons-material/CheckCircle";
import UndoIcon from "@mui/icons-material/Undo";
import UploadIcon from "@mui/icons-material/UploadFile";
import DescriptionIcon from "@mui/icons-material/Description";
import ScanIcon from "@mui/icons-material/DocumentScanner";
import { contractsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { STAGE } from "@/components/Stage";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { useAppSelector } from "@/store";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import type { ContractItem, ContractStatus } from "@/types";
import type { RefData } from "./AdminHome";
import { fmtMoney } from "./CompaniesTab";
import { CONTRACTS_CHANGED, ContractWizard, saveBlob, StatusChip } from "./ContractWizard";
import { usePersisted } from "@/hooks/usePersisted";

const FILTERS: ("all" | ContractStatus)[] = ["all", "draft", "signed", "returned", "approved"];
const dt = (s?: string | null) => (s ? formatDateTime(new Date(s + "Z")) : "—");
/** Holat rangi — faqat chap chiziq va belgi uchun (fon o'zgarmaydi: yorug'/qorong'i rejimda ham o'qiladi). */
export const STATUS_EDGE: Record<ContractStatus, string> = { draft: "text.disabled", signed: STAGE.yellow.border, returned: "error.main", approved: "success.main" };
const openBlob = (p: Promise<Blob>, fail: (e: unknown) => void) => {
  const w = window.open("", "_blank");
  p.then((b) => { const u = URL.createObjectURL(b); if (w) w.location.href = u; }).catch((e) => { w?.close(); fail(e); });
};
export function AwaitChip({ c }: { c: ContractItem }) {
  const { t } = useI18n();
  if (!c.awaiting_scan) return null;
  const pdf = c.source === "manual" || c.source === "import";
  return <Chip size="small" color="warning" variant="outlined" icon={<UploadIcon />} data-awaiting={pdf ? "pdf" : "scan"}
    label={t(pdf ? "ctr_await_pdf" : "ctr_await_scan")} sx={{ fontWeight: 600 }} />;
}

export function UsageBar({ c }: { c: Pick<ContractItem, "used_m3" | "annual_volume" | "usage_pct" | "usage_level"> }) {
  const { t } = useI18n();
  if (!c.annual_volume) return <Typography variant="caption" color="text.secondary">—</Typography>;
  const color = c.usage_level === "over" ? "error" : c.usage_level === "warn" ? "warning" : "success";
  return (
    <Box sx={{ minWidth: 120 }} data-usage={c.usage_level}>
      <Typography variant="caption">{c.used_m3 ?? 0} / {c.annual_volume} m³ ({c.usage_pct ?? 0}%)</Typography>
      <LinearProgress variant="determinate" value={Math.min(100, c.usage_pct ?? 0)} color={color} sx={{ height: 6, borderRadius: 3 }} />
      {c.usage_level !== "ok" && <Typography variant="caption" color={`${color}.main`} fontWeight={600}>{t(c.usage_level === "over" ? "ctr_usage_over" : "ctr_usage_warn")}</Typography>}
    </Box>
  );
}

/** «Shartnomalar»: legal — qilingan shartnomalar (yashil — tasdiqlangan, sariq — kutilmoqda, qizil — qaytarilgan);
 *  buxgalter — tasdiq navbati (standart filtr «Tasdiq kutilmoqda»). */
export function ContractsTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const isLegal = can("customers.contract");
  const isAcc = can("accounting.payments");
  const role = useAppSelector((st) => st.auth.user?.role);  // legal uchun «Yangi shartnoma» yorliqlar qatorida turadi
  const accView = isAcc && !isLegal;  // buxgalter: ikki bo'lim, kartalar
  const [filter, setFilter] = usePersisted<(typeof FILTERS)[number]>(`ctr.filter.${isLegal ? "l" : "a"}`, isLegal ? "all" : "signed");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{ items: ContractItem[]; total: number } | null>(null);
  const [counts, setCounts] = useState<Partial<Record<ContractStatus, number>>>({});
  const [open, setOpen] = useState<number | null>(null);
  const [startReturn, setStartReturn] = useState(false);
  const [wizard, setWizard] = useState<{ id?: number } | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => { const h = window.setTimeout(() => setQuery(q.trim()), 300); return () => window.clearTimeout(h); }, [q]);
  const load = useCallback(() => {
    contractsApi.list({ status: filter === "all" ? undefined : filter, q: query || undefined, limit: 300 }).then(setData).catch(fail);
    contractsApi.list({ status: "signed,returned,draft", limit: 500 }).then((r) => {
      const c: Partial<Record<ContractStatus, number>> = {};
      r.items.forEach((x) => { c[x.status] = (c[x.status] ?? 0) + 1; });
      setCounts(c);
    }).catch(() => undefined);
  }, [filter, query, fail]);
  useEffect(() => {
    load();
    window.addEventListener(CONTRACTS_CHANGED, load);
    return () => window.removeEventListener(CONTRACTS_CHANGED, load);
  }, [load]);

  const approve = async (c: ContractItem) => {
    setBusyId(c.id);
    try { await contractsApi.approve(c.id); toast(t("ctr_approved_ok"), "success"); load(); } catch (e) { fail(e); } finally { setBusyId(null); }
  };
  const view = (id: number, ret = false) => { setStartReturn(ret); setOpen(id); };
  const sections = accView && data ? (["paper", "electronic"] as const).map((m) => ({
    m, items: data.items.filter((c) => (c.sign_method === "electronic" ? "electronic" : "paper") === m) })) : [];

  return (
    <Stack spacing={2} id="contracts">
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }} useFlexGap flexWrap="wrap">
          <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)} id="ctr-filter" sx={{ flexWrap: "wrap" }}>
            {FILTERS.map((f) => <ToggleButton key={f} value={f} data-filter={f}>{t(f === "all" ? "gf_all" : `cs_${f}` as MessageKey)}
              {f !== "all" && f !== "approved" && counts[f] ? <Chip size="small" label={counts[f]} sx={{ ml: 0.75, height: 18 }}
                color={f === "returned" ? "error" : f === "signed" ? "warning" : "default"} /> : null}</ToggleButton>)}
          </ToggleButtonGroup>
          <TextField size="small" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ctr_search")} sx={{ minWidth: 260, flex: 1 }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> }} />
          {isLegal && role !== "legal" && <Button id="ctr-new" size="large" variant="contained" disableElevation startIcon={<NoteAddIcon />} onClick={() => setWizard({})}
            sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("new_contract")}</Button>}
        </Stack>
      </Paper>
      {accView ? sections.map(({ m, items }) => (
        <Paper key={m} variant="outlined" sx={{ p: 2 }} id={`ctr-sec-${m}`} data-section={m}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
            {m === "paper" ? <ScanIcon color="action" /> : <DescriptionIcon color="action" />}
            <Typography variant="h6" fontWeight={700}>{t(m === "paper" ? "ctr_sec_paper" : "ctr_sec_electronic")}</Typography>
            <Chip size="small" label={items.length} data-count={items.length} color={items.length ? "primary" : "default"} sx={{ fontWeight: 700 }} />
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{t(m === "paper" ? "ctr_sec_paper_hint" : "ctr_sec_electronic_hint")}</Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr", xl: "1fr 1fr 1fr" } }}>
            {items.map((c) => <ContractCard key={c.id} c={c} district={districts.find((d) => d.id === c.customer?.district_id)?.name}
              busy={busyId === c.id} onOpen={() => view(c.id)} onApprove={() => approve(c)} onReturn={() => view(c.id, true)} fail={fail} />)}
          </Box>
          {!items.length && <Typography color="text.secondary">{t("ctr_none")}</Typography>}
        </Paper>
      )) : <Paper variant="outlined" sx={{ p: 2 }}>
        <TableContainer><Table size="small" id="ctr-table">
          <TableHead><TableRow>
            <TableCell>{t("contract_no")}</TableCell><TableCell>{t("cmp_name")}</TableCell><TableCell>{t("district")}</TableCell>
            <TableCell>{t("contract_type")}</TableCell><TableCell align="right">{t("ctr_total")}</TableCell><TableCell>{t("ctr_period")}</TableCell>
            <TableCell>{t("ctr_usage")}</TableCell><TableCell>{t("inv_status")}</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {data?.items.map((c) => (
              <TableRow key={c.id} hover data-contract={c.number} onClick={() => view(c.id)} sx={{ cursor: "pointer" }}>
                <TableCell sx={{ fontFamily: "ui-monospace, monospace", whiteSpace: "nowrap", borderLeft: 4, borderLeftColor: STATUS_EDGE[c.status] }}>{c.display_number || "—"}
                  {c.platform_id && <Typography variant="caption" display="block" color="text.secondary">{c.number}</Typography>}
                  {c.source && c.source !== "flow" && <Typography variant="caption" display="block" color="text.secondary">{t("ctr_src_" + c.source as MessageKey)}</Typography>}</TableCell>
                <TableCell>{c.customer?.name} <Typography component="span" variant="caption" sx={{ fontFamily: "ui-monospace, monospace" }}>{c.customer?.code}</Typography></TableCell>
                <TableCell>{districts.find((d) => d.id === c.customer?.district_id)?.name}</TableCell>
                <TableCell>{t(`ct_${c.type}` as MessageKey)}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>{fmtMoney(c.total)}</TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{c.valid_from} — {c.valid_to}</TableCell>
                <TableCell><UsageBar c={c} /></TableCell>
                <TableCell><Stack spacing={0.5} alignItems="flex-start"><StatusChip status={c.status} /><AwaitChip c={c} /></Stack></TableCell>
              </TableRow>
            ))}
            {data && !data.items.length && <TableRow><TableCell colSpan={8}><Typography color="text.secondary">{t("ctr_none")}</Typography></TableCell></TableRow>}
          </TableBody>
        </Table></TableContainer>
      </Paper>}
      {open !== null && <ContractView id={open} isLegal={isLegal} isAcc={isAcc} districts={districts} startReturn={startReturn} onClose={() => setOpen(null)}
        onChanged={load} onEdit={(id) => { setOpen(null); setWizard({ id }); }} />}
      {wizard && <ContractWizard districts={districts} contractId={wizard.id} onClose={() => setWizard(null)} onDone={load} />}
    </Stack>
  );
}

/** Buxgalter navbatidagi karta: mavzuga mos fon, chapda holat rangi, katta yozuv, amallar kartaning o'zida. */
function ContractCard({ c, district, busy, onOpen, onApprove, onReturn, fail }: { c: ContractItem; district?: string; busy: boolean;
  onOpen: () => void; onApprove: () => void; onReturn: () => void; fail: (e: unknown) => void }) {
  const { t } = useI18n();
  const kv = (k: MessageKey, v?: string | number | null) => <Box sx={{ minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" display="block">{t(k)}</Typography>
    <Typography variant="body1" fontWeight={600} sx={{ overflowWrap: "anywhere" }}>{v ?? "—"}</Typography></Box>;
  return (
    <Paper variant="outlined" data-card-contract={c.display_number} data-status={c.status}
      sx={{ p: 2, bgcolor: "background.paper", color: "text.primary", borderLeft: 6, borderLeftColor: STATUS_EDGE[c.status], display: "flex", flexDirection: "column", gap: 1.25 }}>
      <Stack direction="row" spacing={1} alignItems="flex-start" justifyContent="space-between">
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" fontWeight={700} lineHeight={1.25} sx={{ overflowWrap: "anywhere" }}>{c.customer?.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            <Box component="span" sx={{ fontFamily: "ui-monospace, monospace" }}>{c.customer?.code}</Box>{district ? ` · ${district}` : ""}</Typography>
        </Box>
        <StatusChip status={c.status} />
      </Stack>
      <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: "1fr 1fr" }}>
        {kv(c.platform_id ? "ctr_platform_id" : "contract_no", c.platform_id ? `${c.platform_id}${c.platform ? ` (${t(`ctr_pl_${c.platform}` as MessageKey)})` : ""}` : c.display_number || "—")}
        {kv("ctr_internal_no", c.number)}
        {kv("contract_type", t(`ct_${c.type}` as MessageKey))}{kv("ctr_annual_volume", c.annual_volume != null ? `${c.annual_volume} m³` : null)}
        {kv("ctr_total", fmtMoney(c.total))}{kv("ctr_period", `${c.valid_from} — ${c.valid_to}`)}
        {kv("signed_on", c.signed_on ? `${c.signed_on} · ${t(c.sign_method === "electronic" ? "sm_electronic" : "sm_paper")}` : null)}
        {kv("ctr_submitted", c.submitted_by ? `${c.submitted_by}${c.signed_at ? ` · ${dt(c.signed_at)}` : ""}` : null)}
      </Box>
      {c.source && c.source !== "flow" && <Typography variant="caption" color="text.secondary">{t("ctr_src_" + c.source as MessageKey)}</Typography>}
      {c.status === "returned" && c.return_comment && <Alert severity="error" variant="outlined" sx={{ py: 0 }}>{c.return_comment}</Alert>}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: "auto", pt: 0.5 }}>
        {c.status === "signed" && <>
          <Button size="medium" variant="contained" disableElevation startIcon={<CheckIcon />} disabled={busy} data-act="approve" onClick={onApprove}
            sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("ctr_approve")}</Button>
          <Button size="medium" color="error" variant="outlined" startIcon={<UndoIcon />} disabled={busy} data-act="return" onClick={onReturn}>{t("ctr_return")}</Button>
        </>}
        <Button size="medium" variant="outlined" startIcon={<DescriptionIcon />} data-act="doc" onClick={() => openBlob(contractsApi.document(c.id, "pdf"), fail)}>{t("ctr_doc")}</Button>
        {c.has_scan && <Button size="medium" variant="outlined" startIcon={<ScanIcon />} data-act="scan" onClick={() => openBlob(contractsApi.scan(c.id), fail)}>{t("ctr_scan")}</Button>}
        <Button size="medium" data-act="open" onClick={onOpen}>{t("ctr_open")}</Button>
      </Stack>
    </Paper>
  );
}

function ContractView({ id, isLegal, isAcc, districts, startReturn, onClose, onChanged, onEdit }: { id: number; isLegal: boolean; isAcc: boolean;
  districts: RefData["districts"]; startReturn?: boolean; onClose: () => void; onChanged: () => void; onEdit: (id: number) => void }) {
  const { t, tErr } = useI18n();
  const [c, setC] = useState<ContractItem | null>(null);
  const [ret, setRet] = useState<string | null>(startReturn ? "" : null);
  const pdfRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  useEffect(() => { contractsApi.get(id).then(setC).catch(fail); }, [id, fail]);
  const act = async (fn: () => Promise<ContractItem>, msg: MessageKey) => {
    setBusy(true);
    try { setC(await fn()); toast(t(msg), "success"); setRet(null); onChanged(); window.dispatchEvent(new Event(CONTRACTS_CHANGED)); } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const openDoc = (p: Promise<Blob>) => openBlob(p, fail);
  if (!c) return null;
  const needPdf = c.awaiting_scan && (c.source === "manual" || c.source === "import");
  const cu = c.customer;
  const row = (k: MessageKey, v?: string | number | null) => <Box><Typography variant="caption" color="text.secondary">{t(k)}</Typography>
    <Typography variant="body2">{v ?? "—"}</Typography></Box>;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" id="ctr-view">
      <DialogTitle sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
        {t("ctr_title_n", { n: c.display_number })} <StatusChip status={c.status} /> <AwaitChip c={c} />
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {c.status === "returned" && c.return_comment && <Alert severity="error"><b>{t("ctr_returned_by")}</b> {c.return_comment}</Alert>}
          {c.status === "signed" && <Alert severity="warning" variant="outlined">{t("ctr_pending_hint")}</Alert>}
          {c.awaiting_scan && <Alert severity="warning" id="ctr-await-alert">{t(needPdf ? "ex_pdf_hint" : "ctr_paper_wait_hint")}</Alert>}
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" } }}>
            {row("cmp_name", cu?.name)}{row("stir", cu?.stir)}{row("district", districts.find((d) => d.id === cu?.district_id)?.name)}{row("director", cu?.director)}
            {row("ctr_f_account", cu?.account)}{row("ctr_f_mfo", cu?.mfo)}{row("ctr_f_bank", cu?.bank)}{row("phone", cu?.phone)}
            {row("contract_type", t(`ct_${c.type}` as MessageKey))}{row("ctr_price", c.price != null ? fmtMoney(c.price) : null)}
            {row("ctr_annual_volume", c.annual_volume)}{row("ctr_total", fmtMoney(c.total))}
            {row("ctr_internal_no", c.number)}{row("ctr_platform_id", c.platform_id ? `${c.platform_id} (${t(`ctr_pl_${c.platform}` as MessageKey)})` : null)}
            {row("signed_on", c.signed_on)}{row("ctr_period", `${c.valid_from} — ${c.valid_to}`)}
          </Box>
          <UsageBar c={c} />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button size="small" variant="outlined" onClick={() => openDoc(contractsApi.document(c.id, "pdf"))}>{t("ctr_open_pdf")}</Button>
            <Button size="small" variant="outlined" onClick={() => contractsApi.document(c.id, "docx").then((b) => saveBlob(b, `shartnoma_${(c.number ?? "loyiha").replace(/\W+/g, "_")}.docx`)).catch(fail)}>{t("ctr_word")}</Button>
            {c.has_scan && <Button size="small" variant="outlined" id="ctr-scan" onClick={() => openDoc(contractsApi.scan(c.id))}>{t("ctr_scan")}</Button>}
          </Stack>
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{t("ctr_history")}</Typography>
            {c.events?.map((e, i) => <Typography key={i} variant="body2" data-event={e.action}>
              {dt(e.at)} · <b>{t(`ce_ev_${e.action}` as MessageKey)}</b> · {e.actor ?? "—"}{e.comment ? ` — «${e.comment}»` : ""}</Typography>)}
          </Box>
          {ret !== null && <TextField id="ctr-return-comment" autoFocus multiline minRows={2} label={t("ctr_return_comment")} value={ret}
            onChange={(e) => setRet(e.target.value)} helperText={t("ctr_return_hint")} />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        {isLegal && needPdf && <>
          <input ref={pdfRef} type="file" hidden accept="application/pdf,.pdf" id="ctr-pdf-file" onChange={(e) => {
            const f = e.target.files?.[0]; e.target.value = "";
            if (f) act(() => contractsApi.uploadScan(c.id, f), "ctr_pdf_uploaded");
          }} />
          <Button id="ctr-upload-pdf" variant="contained" color="warning" disableElevation startIcon={<UploadIcon />} disabled={busy}
            onClick={() => pdfRef.current?.click()}>{t("ctr_upload_pdf")}</Button>
        </>}
        {isLegal && !needPdf && (c.status === "draft" || c.status === "returned") && <Button id="ctr-continue" variant="contained" disableElevation onClick={() => onEdit(c.id)}>
          {t(c.status === "returned" ? "ctr_fix" : "ctr_continue")}</Button>}
        <Box sx={{ flex: 1 }} />
        {isAcc && c.status === "signed" && (ret === null
          ? <>
            <Button id="ctr-return" color="error" variant="outlined" startIcon={<UndoIcon />} onClick={() => setRet("")} disabled={busy}>{t("ctr_return")}</Button>
            <Button id="ctr-approve" variant="contained" disableElevation startIcon={<CheckIcon />} disabled={busy}
              onClick={() => act(() => contractsApi.approve(c.id), "ctr_approved_ok")} sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>
              {t("ctr_approve")}</Button>
          </>
          : <>
            <Button onClick={() => setRet(null)} disabled={busy}>{t("cancel")}</Button>
            <Button id="ctr-return-send" color="error" variant="contained" disableElevation disabled={busy || ret.trim().length < 3}
              onClick={() => act(() => contractsApi.returnBack(c.id, ret.trim()), "ctr_returned_ok")}>{t("ctr_return_send")}</Button>
          </>)}
        <Button onClick={onClose}>{t("close")}</Button>
      </DialogActions>
    </Dialog>
  );
}
