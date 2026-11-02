import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Autocomplete, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, IconButton,
  MenuItem, Paper, Radio, RadioGroup, Stack, Step, StepLabel, Stepper, TextField, ToggleButton, ToggleButtonGroup, Typography, useMediaQuery,
  useTheme } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import DescriptionIcon from "@mui/icons-material/Description";
import DrawIcon from "@mui/icons-material/Draw";
import { contractsApi, customersApi, tariffsApi } from "@/api/endpoints";
import { onlyDigits } from "@/components/DigitsField";
import { errorCode, errorMessage } from "@/api/client";
import { STAGE } from "@/components/Stage";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { ContractCheck, ContractDraft, ContractItem, ContractType, CustomerListItem, District, Requisites } from "@/types";
import { fmtMoney } from "./CompaniesTab";
import { ExistingImport } from "./ExistingContracts";

const PLATFORMS = ["didox", "hujjat", "soliq", "other"] as const;
const EX_TYPES: ContractType[] = ["by_volume", "per_trip", "monthly", "one_off"];
const todayIso = () => new Date(Date.now() + 5 * 3600_000).toISOString().slice(0, 10);
const yearEnd = () => `${todayIso().slice(0, 4)}-12-31`;
const EMPTY_REQ: Requisites = { name: "", stir: "", director: "", phone: "", legal_address: "", address: "", bank: "", mfo: "", account: "",
  oked: "", cadastre: "", is_rented: false };
type ReqText = Exclude<keyof Requisites, "is_rented">;
const REQ_FIELDS: { k: ReqText; span: number; digits?: number }[] = [
  { k: "name", span: 2 }, { k: "stir", span: 1, digits: 9 }, { k: "director", span: 2 }, { k: "phone", span: 1 },
  { k: "legal_address", span: 3 }, { k: "address", span: 2 }, { k: "cadastre", span: 1 },
  { k: "bank", span: 2 }, { k: "mfo", span: 1, digits: 5 }, { k: "account", span: 2, digits: 20 }, { k: "oked", span: 1, digits: 5 },
];

/** Shartnoma o'zgarganda ro'yxatlar yangilanadi (ustani qayerdan ochilganidan qat'i nazar). */
export const CONTRACTS_CHANGED = "csw:contracts-changed";
const changed = () => window.dispatchEvent(new Event(CONTRACTS_CHANGED));

export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

interface Props { districts: District[]; contractId?: number; onClose: () => void; onDone?: (c: ContractItem) => void }

/** «Yangi shartnoma»: 1) korxona 2) rekvizitlar va shartlar → «Tekshirish» → raqam 3) hujjat (PDF/Word) → «Imzolandi — buxgalteriyaga yuborish». */
export function ContractWizard({ districts, contractId, onClose, onDone }: Props) {
  const { t, tErr } = useI18n();
  const theme = useTheme();
  const mobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [step, setStep] = useState(contractId ? -1 : 0);
  const [ct, setCt] = useState<ContractItem | null>(null);
  const [customer, setCustomer] = useState<{ id: number; name: string; district_id: number } | null>(null);
  const [form, setForm] = useState<Omit<ContractDraft, "customer_id">>({ requisites: EMPTY_REQ, type: "by_volume", price: null, annual_volume: null,
    annual_trips: null, valid_from: todayIso(), valid_to: yearEnd(), place: "", sign_method: "electronic" });
  const [checked, setChecked] = useState<ContractCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const districtName = (id?: number) => districts.find((d) => d.id === id)?.name ?? "";

  const [tariff, setTariff] = useState<number | null | undefined>(undefined);
  // Boshlang'ich tanlov: yangi shartnoma tuzish yoki mavjud (imzolangan) shartnomani kiritish (bittalab / Excel)
  const [mode, setMode] = useState<"new" | "existing" | "excel">("new");
  // Mavjud shartnoma: yangi bilan bir xil forma + raqam, imzolangan sana, platforma ID, skan → buxgalter tasdig'iga
  const [ex, setEx] = useState({ number: "", signed_on: "", platform: "didox", platform_id: "" });
  const [exFile, setExFile] = useState<File | null>(null);
  const exFileRef = useRef<HTMLInputElement>(null);
  const isEx = mode === "existing";
  const fromCustomer = (c: Partial<Requisites> & { name: string }) => ({ ...EMPTY_REQ, ...Object.fromEntries(Object.entries(c)
    .filter(([k]) => k in EMPTY_REQ).map(([k, v]) => [k, k === "is_rented" ? !!v : v ?? ""])) } as Requisites);
  const fromContract = useCallback((c: ContractItem) => {
    setCt(c);
    if (c.customer) {
      setCustomer({ id: c.customer.id, name: c.customer.name, district_id: c.customer.district_id });
      const d = c.draft;
      setForm({ requisites: fromCustomer(d?.requisites ?? c.customer), type: "by_volume", price: c.price,
        annual_volume: d?.annual_volume ?? c.annual_volume, annual_trips: null, valid_from: d?.valid_from ?? c.valid_from,
        valid_to: d?.valid_to ?? c.valid_to, place: d?.place ?? c.place ?? districtName(c.customer.district_id),
        sign_method: d?.sign_method ?? c.sign_method ?? "electronic" });
    }
    // Tugallanmagan (raqamsiz yoki tekshirilmagan o'zgarishlar) va qaytarilgan — forma; aks holda hujjat
    setStep(c.status === "returned" || !c.number || c.draft ? 1 : 2);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { if (contractId) contractsApi.get(contractId).then(fromContract).catch(fail); }, [contractId, fromContract, fail]);
  // Narx — davlat ta'rifi (tuman → viloyat), shartnoma boshlanish sanasidagi; qo'lda kiritilmaydi
  useEffect(() => {
    if (!customer || !form.valid_from) return;
    tariffsApi.price(customer.district_id, form.valid_from).then((r) => setTariff(r.price)).catch(() => setTariff(null));
  }, [customer, form.valid_from]);

  const pickCustomer = async (id: number) => {
    if (mode === "existing") {
      try {
        const c = await customersApi.get(id);
        setCustomer({ id: c.id, name: c.name, district_id: c.district_id });
        setForm((f) => ({ ...f, place: f.place || districtName(c.district_id), sign_method: "paper", requisites: fromCustomer(c as unknown as Requisites) }));
        setChecked(null);
        setStep(1);
      } catch (e) { fail(e); }
      return;
    }
    try {
      const c = await customersApi.get(id);
      const draft = await contractsApi.start(c.id);  // «Tugallanmagan shartnomalar»da darhol paydo bo'ladi
      changed();
      setCt(draft);
      setCustomer({ id: c.id, name: c.name, district_id: c.district_id });
      setForm((f) => ({ ...f, place: f.place || districtName(c.district_id), requisites: fromCustomer(c as unknown as Requisites) }));
      setChecked(null);
      setStep(1);
    } catch (e) { fail(e); }
  };

  const payload = (): ContractDraft => ({ ...form, type: isEx ? form.type : "by_volume", customer_id: customer!.id,
    existing: isEx ? { number: ex.number.trim(), signed_on: ex.signed_on || null, platform: form.sign_method === "electronic" ? ex.platform : null,
      platform_id: form.sign_method === "electronic" ? ex.platform_id.trim() || null : null } : null, requisites: Object.fromEntries(Object.entries(form.requisites)
    .map(([k, v]) => [k, typeof v === "string" ? v.trim() || null : v])) as unknown as Requisites });
  /** Yopish yoki «Saqlab chiqish»: forma tekshiruvsiz loyihaga yoziladi (keyin «Davom etish»). */
  const close = async () => {
    if (step === 1 && ct && (ct.status === "draft" || ct.status === "returned") && !busy) {
      try { await contractsApi.saveDraft(ct.id, payload()); changed(); toast(t("ctr_draft_saved")); } catch { /* jim */ }
    }
    onClose();
  };
  const runCheck = async () => {
    setBusy(true);
    try {
      const r = await contractsApi.check(payload(), ct?.id);
      setChecked(r);
      toast(r.ok ? t("ctr_check_ok") : t("ctr_check_bad", { n: r.errors.length }), r.ok ? "success" : "warning");
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    if (isEx) {
      try {
        const c = await contractsApi.createExisting(payload());
        if (exFile) await contractsApi.uploadScan(c.id, exFile);
        changed(); toast(t("ex_saved_pending", { n: c.display_number }), "success"); onDone?.(c); onClose();
      } catch (e) { fail(e); } finally { setBusy(false); }
      return;
    }
    try {
      const c = ct ? await contractsApi.update(ct.id, payload()) : await contractsApi.create(payload());
      setCt(c); setStep(2); changed();
      toast(t("ctr_saved", { n: c.number ?? "" }), "success");
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const errOf = (f: string) => checked?.errors.find((e) => e.field === f);
  const setReq = (k: ReqText, v: string) => { setForm({ ...form, requisites: { ...form.requisites, [k]: v } }); setChecked(null); };
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => { setForm({ ...form, [k]: v }); setChecked(null); };
  const helper = (f: string, hint?: string) => {
    const e = errOf(f);
    return e ? t(`ce_${e.code}` as MessageKey) : hint ? t("ctr_digits", { n: hint }) : undefined;
  };

  const steps = [t("ctr_step_customer"), t("ctr_step_data"), t("ctr_step_doc")];
  return (
    <Dialog open onClose={() => !busy && close()} fullWidth maxWidth="lg" fullScreen={mobile} id="contract-wizard">
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1, pr: 6 }}>
        {ct?.number ? t("ctr_title_n", { n: ct.display_number }) : t("new_contract")}
        {ct && <StatusChip status={ct.status} />}
        <IconButton onClick={close} sx={{ position: "absolute", right: 8, top: 8 }} aria-label={t("close")}><CloseIcon /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {step >= 0 && <Stepper activeStep={step} alternativeLabel sx={{ mb: 2.5 }}>{steps.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}</Stepper>}
        {ct?.status === "returned" && ct.return_comment && <Alert severity="error" sx={{ mb: 2 }} id="ctr-returned">
          <b>{t("ctr_returned_by")}</b> {ct.return_comment}</Alert>}
        {step === 0 && <Stack spacing={2}>
          <ToggleButtonGroup exclusive fullWidth value={mode} onChange={(_, v) => { if (v) { setMode(v); setCustomer(null); } }} id="ctr-mode"
            sx={{ flexWrap: { xs: "wrap", sm: "nowrap" } }}>
            <ToggleButton value="new" data-mode="new">{t("ctr_mode_new")}</ToggleButton>
            <ToggleButton value="existing" data-mode="existing">{t("ctr_mode_existing")}</ToggleButton>
            <ToggleButton value="excel" data-mode="excel">{t("ctr_mode_excel")}</ToggleButton>
          </ToggleButtonGroup>
          {mode === "excel" ? <ExistingImport fail={fail} onDone={() => { changed(); }} />
            : <CustomerStep districts={districts} onPick={pickCustomer} fail={fail} />}
        </Stack>}
        {step === 1 && customer && <Stack spacing={2}>
          <Typography variant="subtitle2" color="text.secondary">{t("ctr_requisites")} · {districtName(customer.district_id)}</Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
            {REQ_FIELDS.map((f) => f.k === "cadastre"
              ? <Stack key={f.k} direction="row" spacing={1} alignItems="flex-start">
                <TextField size="small" name="cadastre" label={`${t("ctr_f_cadastre")} (${t("ctr_optional_short")})`} value={form.requisites.cadastre ?? ""}
                  onChange={(e) => setReq("cadastre", e.target.value)} sx={{ flex: 1 }} />
                <FormControlLabel sx={{ mr: 0, whiteSpace: "nowrap" }} label={t("ctr_rented")} control={<Checkbox size="small" name="is_rented"
                  checked={!!form.requisites.is_rented} onChange={(e) => { setForm({ ...form, requisites: { ...form.requisites, is_rented: e.target.checked } }); setChecked(null); }} />} />
              </Stack>
              : <TextField key={f.k} size="small" name={f.k} label={t(`ctr_f_${f.k}` as MessageKey)} value={form.requisites[f.k] ?? ""}
              onChange={(e) => setReq(f.k, f.digits ? onlyDigits(e.target.value, f.digits) : e.target.value)} error={!!errOf(f.k)}
              helperText={helper(f.k, f.digits && f.k !== "oked" ? String(f.digits) : undefined)}
              inputProps={f.digits ? { inputMode: "numeric", maxLength: f.digits } : undefined}
              sx={{ gridColumn: { md: `span ${f.span}` } }} />)}
          </Box>
          <Divider />
          <Typography variant="subtitle2" color="text.secondary">{t("ctr_terms")}</Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(4, 1fr)" } }}>
            {isEx
              ? <TextField select size="small" name="type" label={t("contract_type")} value={form.type} onChange={(e) => set("type", e.target.value as ContractType)}>
                {EX_TYPES.map((x) => <MenuItem key={x} value={x}>{t(`ct_${x}` as MessageKey)}</MenuItem>)}
              </TextField>
              : <TextField size="small" label={t("contract_type")} value={t("ct_by_volume")} InputProps={{ readOnly: true }} />}
            {isEx && form.type !== "by_volume"
              ? <TextField size="small" name="price" type="number" label={`${t("ctr_price")} (${t("ctr_vat_incl")})`} value={form.price ?? ""}
                  onChange={(e) => set("price", e.target.value === "" ? null : Number(e.target.value))} error={!!errOf("price")} helperText={helper("price")} />
              : <TextField size="small" name="price" label={t("ctr_price_tariff")} InputProps={{ readOnly: true }} id="ctr-tariff"
                  value={tariff ? fmtMoney(tariff) : tariff === null ? t("ctr_no_tariff") : "…"}
                  error={tariff === null || !!errOf("price")} helperText={errOf("price") ? helper("price") : t("ctr_tariff_hint")} />}
            <TextField size="small" name="annual_volume" type="number" label={t("ctr_annual_volume")} value={form.annual_volume ?? ""}
              onChange={(e) => set("annual_volume", e.target.value === "" ? null : Number(e.target.value))}
              error={!!errOf("annual_volume")} helperText={helper("annual_volume")} />
            <TextField size="small" name="place" label={t("ctr_place")} value={form.place} onChange={(e) => set("place", e.target.value)}
              error={!!errOf("place")} helperText={helper("place")} />
            <TextField size="small" name="valid_from" type="date" label={t("valid_from")} value={form.valid_from} InputLabelProps={{ shrink: true }}
              onChange={(e) => set("valid_from", e.target.value)} error={!!errOf("valid_from")} helperText={helper("valid_from")} />
            <TextField size="small" name="valid_to" type="date" label={t("valid_to")} value={form.valid_to} InputLabelProps={{ shrink: true }}
              onChange={(e) => set("valid_to", e.target.value)} error={!!errOf("valid_to")} helperText={helper("valid_to")} />
            <Box>
              <Typography variant="caption" color="text.secondary">{t("ctr_sign_method")}</Typography>
              <RadioGroup row value={form.sign_method} onChange={(e) => set("sign_method", e.target.value as "electronic" | "paper")}>
                <FormControlLabel value="electronic" control={<Radio size="small" />} label={t("ctr_m_electronic")} />
                <FormControlLabel value="paper" control={<Radio size="small" />} label={t("ctr_m_paper")} />
              </RadioGroup>
            </Box>
          </Box>
          {isEx && <>
            <Divider />
            <Typography variant="subtitle2" color="text.secondary">{t("ex_meta")}</Typography>
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(4, 1fr)" } }} id="ex-meta">
              <TextField size="small" name="ex_number" label={t("contract_no")} value={ex.number} required
                onChange={(e) => { setEx({ ...ex, number: e.target.value }); setChecked(null); }} error={!!errOf("number")} helperText={helper("number")} />
              <TextField size="small" name="ex_signed" type="date" label={t("signed_on")} value={ex.signed_on} InputLabelProps={{ shrink: true }}
                inputProps={{ max: todayIso() }} onChange={(e) => { setEx({ ...ex, signed_on: e.target.value }); setChecked(null); }}
                error={!!errOf("signed_on")} helperText={helper("signed_on")} />
              {form.sign_method === "electronic" && <>
                <TextField size="small" select label={t("ctr_platform")} value={ex.platform} onChange={(e) => setEx({ ...ex, platform: e.target.value })}>
                  {PLATFORMS.map((p) => <MenuItem key={p} value={p}>{t(`ctr_pl_${p}` as MessageKey)}</MenuItem>)}
                </TextField>
                <TextField size="small" name="ex_pid" label={t("ctr_platform_id")} value={ex.platform_id}
                  onChange={(e) => { setEx({ ...ex, platform_id: e.target.value }); setChecked(null); }} error={!!errOf("platform_id")} helperText={helper("platform_id")} />
              </>}
              <Box>
                <input ref={exFileRef} type="file" hidden accept="application/pdf,image/jpeg,image/png" onChange={(e) => setExFile(e.target.files?.[0] ?? null)} />
                <Button size="small" onClick={() => exFileRef.current?.click()}>{t("ctr_attach_scan")}</Button>
                {exFile && <Chip size="small" label={exFile.name} onDelete={() => setExFile(null)} sx={{ ml: 1 }} />}
              </Box>
            </Box>
          </>}
          {checked && <Paper variant="outlined" id="ctr-totals" sx={{ p: 2, borderColor: checked.ok ? STAGE.green.bg : "warning.main", borderWidth: 2 }}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={3} useFlexGap flexWrap="wrap">
              <Box><Typography variant="caption" color="text.secondary">{t("ctr_qty")}</Typography>
                <Typography fontWeight={600}>{checked.totals.qty} {checked.totals.unit}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">{t("ctr_net")}</Typography><Typography>{fmtMoney(checked.totals.net)}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">{t("inv_vat")} 12%</Typography><Typography>{fmtMoney(checked.totals.vat)}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">{t("ctr_total")}</Typography>
                <Typography fontWeight={700} data-total>{fmtMoney(checked.totals.total)}</Typography></Box>
            </Stack>
            <Typography variant="body2" sx={{ mt: 1 }} data-words>{checked.totals.words}</Typography>
            {!checked.ok && <Alert severity="warning" sx={{ mt: 1 }}>{t("ctr_fix_errors")}</Alert>}
          </Paper>}
        </Stack>}
        {step === 2 && ct && <DocStep ct={ct} busy={busy} setBusy={setBusy} fail={fail}
          onSigned={(c) => { setCt(c); changed(); toast(t("ctr_signed_ok"), "success"); onDone?.(c); onClose(); }}
          onDeleted={() => { changed(); toast(t("ctr_deleted")); onDone?.(ct); onClose(); }} />}
        {step === -1 && <Typography color="text.secondary">…</Typography>}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 1.5, flexWrap: "wrap", gap: 1 }}>
        {step === 1 && ct && (ct.status === "draft" || ct.status === "returned") &&
          <Button id="ctr-save-exit" onClick={close} disabled={busy}>{t("ctr_save_exit")}</Button>}
        {step === 2 && ct && (ct.status === "draft" || ct.status === "returned") &&
          <Button onClick={() => { setStep(1); setChecked(null); }} disabled={busy} id="ctr-edit">{t("ctr_edit")}</Button>}
        <Box sx={{ flex: 1 }} />
        {step === 1 && <>
          <Button id="ctr-check" variant="outlined" startIcon={<FactCheckIcon />} onClick={runCheck} disabled={busy}>{t("ctr_check")}</Button>
          <Button id="ctr-save" variant="contained" disableElevation onClick={save} disabled={busy || !checked?.ok}
            sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t(isEx ? "ex_send_accountant" : ct ? "ctr_save_changes" : "ctr_save_number")}</Button>
        </>}
      </DialogActions>
    </Dialog>
  );
}

function CustomerStep({ districts, onPick, fail }: { districts: District[]; onPick: (id: number) => void; fail: (e: unknown) => void }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [opts, setOpts] = useState<CustomerListItem[]>([]);
  const [nw, setNw] = useState<{ name: string; district_id: number | "" } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const h = window.setTimeout(() => {
      if (q.trim().length < 2) { setOpts([]); return; }
      customersApi.search({ q: q.trim(), limit: 20 }).then((r) => setOpts(r.items)).catch(() => undefined);
    }, 300);
    return () => window.clearTimeout(h);
  }, [q]);
  const create = async () => {
    if (!nw || nw.name.trim().length < 2 || nw.district_id === "") return;
    setBusy(true);
    try { const c = await customersApi.create({ name: nw.name.trim(), district_id: nw.district_id }); onPick(c.id); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <Stack spacing={2} sx={{ maxWidth: 640, mx: "auto" }}>
      <Autocomplete id="ctr-customer-search" options={opts} filterOptions={(x) => x} getOptionLabel={(o) => `${o.name}${o.code ? ` · ${o.code}` : ""}${o.stir ? ` · ${o.stir}` : ""}`}
        onInputChange={(_, v) => setQ(v)} onChange={(_, v) => v && onPick(v.id)} noOptionsText={q.length < 2 ? t("ctr_type_2") : t("no_results")}
        renderOption={(props, o) => <li {...props} key={o.id}><Box><Typography>{o.name}</Typography>
          <Typography variant="caption" color="text.secondary">{o.code} · {o.stir ?? "—"} · {districts.find((d) => d.id === o.district_id)?.name}</Typography></Box></li>}
        renderInput={(p) => <TextField {...p} label={t("ctr_find_customer")} placeholder={t("ctr_find_hint")} />} />
      <Divider>{t("ctr_or")}</Divider>
      {!nw ? <Button id="ctr-new-customer" variant="outlined" onClick={() => setNw({ name: "", district_id: districts.length === 1 ? districts[0].id : "" })}>
        {t("ctr_new_customer")}</Button>
        : <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <TextField id="ctr-nc-name" size="small" label={t("cmp_name")} value={nw.name} onChange={(e) => setNw({ ...nw, name: e.target.value })} sx={{ flex: 1 }} />
          <TextField id="ctr-nc-district" select size="small" label={t("district")} value={nw.district_id} sx={{ minWidth: 200 }}
            onChange={(e) => setNw({ ...nw, district_id: Number(e.target.value) })}>
            {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
          </TextField>
          <Button id="ctr-nc-create" variant="contained" disableElevation disabled={busy || nw.name.trim().length < 2 || nw.district_id === ""} onClick={create}>
            {t("ctr_continue")}</Button>
        </Stack>}
    </Stack>
  );
}

function DocStep({ ct, busy, setBusy, fail, onSigned, onDeleted }: { ct: ContractItem; busy: boolean; setBusy: (b: boolean) => void;
  fail: (e: unknown) => void; onSigned: (c: ContractItem) => void; onDeleted: () => void }) {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [sign, setSign] = useState({ signed_on: todayIso(), sign_method: ct.sign_method ?? "electronic", platform: ct.platform ?? "didox",
    platform_id: ct.platform_id ?? "" });
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let u: string | null = null;
    contractsApi.document(ct.id, "pdf").then((b) => { u = URL.createObjectURL(b); setUrl(u); }).catch(fail);
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [ct.id, ct.status, fail]);
  const canSign = ct.status === "draft" || ct.status === "returned";
  const electronic = sign.sign_method === "electronic";
  const submit = async () => {
    setBusy(true);
    try {
      onSigned(await contractsApi.sign(ct.id, { signed_on: sign.signed_on, sign_method: sign.sign_method,
        platform: electronic ? sign.platform : undefined, platform_id: electronic ? sign.platform_id.trim() : undefined, file }));
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const remove = async () => {
    if (!window.confirm(t("ctr_delete_confirm"))) return;
    setBusy(true);
    try { await contractsApi.remove(ct.id); onDeleted(); } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const name = `shartnoma_${ct.display_number.replace(/[^\w-]+/g, "_")}`;
  return (
    <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" } }}>
      <Paper variant="outlined" sx={{ height: { xs: 420, md: 640 }, overflow: "hidden" }}>
        {url ? <iframe title="contract" src={url} style={{ width: "100%", height: "100%", border: 0 }} id="ctr-preview" />
          : <Typography sx={{ p: 2 }} color="text.secondary">…</Typography>}
      </Paper>
      <Stack spacing={2}>
        <Box>
          <Typography variant="subtitle2">{ct.customer?.name}</Typography>
          <Typography variant="body2" color="text.secondary">{t("ctr_internal_no")}: <b>{ct.number}</b>{ct.platform_id && <> · {t("ctr_platform_id")}: <b>{ct.platform_id}</b></>}</Typography>
          <Typography variant="body2" color="text.secondary">{fmtMoney(ct.total)} · {ct.valid_from} — {ct.valid_to}</Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button id="ctr-pdf" variant="outlined" startIcon={<PictureAsPdfIcon />} onClick={() => url && window.open(url, "_blank")}>{t("ctr_open_pdf")}</Button>
          <Button id="ctr-docx" variant="outlined" startIcon={<DescriptionIcon />}
            onClick={() => contractsApi.document(ct.id, "docx").then((b) => saveBlob(b, `${name}.docx`)).catch(fail)}>{t("ctr_word")}</Button>
        </Stack>
        <Alert severity="info" variant="outlined">{t(ct.sign_method === "paper" ? "ctr_hint_paper" : "ctr_hint_electronic")}</Alert>
        {canSign && <Paper variant="outlined" sx={{ p: 2 }} id="ctr-sign">
          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("ctr_sign_title")}</Typography>
          <Stack spacing={1.5}>
            <RadioGroup row value={sign.sign_method} onChange={(e) => setSign({ ...sign, sign_method: e.target.value as "electronic" | "paper" })}>
              <FormControlLabel value="electronic" control={<Radio size="small" />} label={t("ctr_m_electronic")} />
              <FormControlLabel value="paper" control={<Radio size="small" />} label={t("ctr_m_paper")} />
            </RadioGroup>
            <TextField size="small" type="date" name="signed_on" label={t("signed_on")} value={sign.signed_on} InputLabelProps={{ shrink: true }}
              inputProps={{ max: todayIso() }} onChange={(e) => setSign({ ...sign, signed_on: e.target.value })} />
            {electronic && <>
              <TextField size="small" select name="platform" label={t("ctr_platform")} value={sign.platform} onChange={(e) => setSign({ ...sign, platform: e.target.value })}>
                {PLATFORMS.map((p) => <MenuItem key={p} value={p}>{t(`ctr_pl_${p}` as MessageKey)}</MenuItem>)}
              </TextField>
              <TextField size="small" name="platform_id" label={t("ctr_platform_id")} value={sign.platform_id} required
                onChange={(e) => setSign({ ...sign, platform_id: e.target.value })} helperText={t("ctr_platform_id_hint")} />
            </>}
            <Box>
              <input ref={fileRef} type="file" hidden accept="application/pdf,image/jpeg,image/png" id="ctr-file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <Button size="small" onClick={() => fileRef.current?.click()}>{t(electronic ? "ctr_attach_signed" : "ctr_attach_scan")}</Button>
              {file && <Chip size="small" label={file.name} onDelete={() => setFile(null)} sx={{ ml: 1 }} />}
            </Box>
            <Button id="ctr-signed" variant="contained" disableElevation size="large" startIcon={<DrawIcon />}
              disabled={busy || !sign.signed_on || (electronic && !sign.platform_id.trim())} onClick={submit}
              sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("ctr_signed_send")}</Button>
          </Stack>
        </Paper>}
        {ct.status === "draft" && <Button color="error" onClick={remove} disabled={busy} id="ctr-delete">{t("ctr_delete")}</Button>}
      </Stack>
    </Box>
  );
}

export function StatusChip({ status }: { status: ContractItem["status"] }) {
  const { t } = useI18n();
  const sx = useMemo(() => ({
    draft: { bgcolor: "action.selected", color: "text.primary" },
    signed: { bgcolor: STAGE.yellow.bg, color: STAGE.yellow.ink },
    returned: { bgcolor: "error.main", color: "#fff" },
    approved: { bgcolor: STAGE.green.bg, color: "#fff" },
  })[status], [status]);
  return <Chip size="small" label={t(`cs_${status}` as MessageKey)} sx={{ ...sx, fontWeight: 600 }} data-status={status} />;
}
