import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, IconButton,
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
import { CoordFields } from "@/components/CoordFields";
import { STAGE } from "@/components/Stage";
import { useCan } from "@/hooks/useCan";
import { MESSAGES } from "@/i18n/messages";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { Appeal, ContractCheck, ContractDraft, ContractItem, ContractType, District, Requisites, StirLookup } from "@/types";
import { fmtMoney } from "./CompaniesTab";
import { ExistingImport } from "./ExistingContracts";

const PLATFORMS = ["didox", "hujjat", "soliq", "other"] as const;
const MapEditor = lazy(() => import("@/components/MapEditor"));  // Leaflet — alohida bo'lak (faqat forma ochilganda yuklanadi)
const EX_TYPES: ContractType[] = ["by_volume", "per_trip", "monthly", "one_off"];
const todayIso = () => new Date(Date.now() + 5 * 3600_000).toISOString().slice(0, 10);
const yearEnd = () => `${todayIso().slice(0, 4)}-12-31`;
const EMPTY_REQ: Requisites = { name: "", stir: "", director: "", phone: "", legal_address: "", address: "", bank: "", mfo: "", account: "",
  oked: "", cadastre: "", is_rented: false, lat: null, lng: null, geofence: null };
type ReqText = Exclude<keyof Requisites, "is_rented" | "lat" | "lng" | "geofence">;
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

interface Props { districts: District[]; contractId?: number; appeal?: Appeal; onClose: () => void; onDone?: (c: ContractItem) => void }

type Mode = "new" | "existing" | "excel";
/** Uch rejim bir-biridan rang, sarlavha va banner bilan ajraladi. */
export const MODE_COLOR: Record<Mode, string> = { new: STAGE.green.bg, existing: "#1E6FD9", excel: "#E07B00" };
const MODE_HOVER: Record<Mode, string> = { new: STAGE.green.border, existing: "#1757AD", excel: "#B86400" };
const EMPTY_EX = { number: "", signed_on: "", platform: "didox", platform_id: "" };
/** Xato maydoni → yorliq kaliti va formadagi input nomi. */
const ERR_LABEL: Record<string, MessageKey> = { price: "ctr_price", price_reason: "ctr_price_reason", annual_volume: "ctr_annual_volume",
  annual_trips: "ctr_annual_trips" as MessageKey, place: "ctr_place", valid_from: "valid_from", valid_to: "valid_to", number: "contract_no",
  signed_on: "signed_on", platform_id: "ctr_platform_id", type: "contract_type", coords: "coords_title" };
const ERR_INPUT: Record<string, string> = { number: "ex_number", signed_on: "ex_signed", platform_id: "ex_pid" };

/** «Shartnoma qo'shish»: forma darhol, eng tepada kontragent STIR'i (korxona = kontragent; my.soliq ulanmaguncha rekvizitlar qo'lda).
 * Yangi shartnoma — faqat bazada yo'q STIR, boshlanish sanasi bugun; STIR shartnomada bor bo'lsa — qo'shimcha shartnoma / filial / manzil so'rovi.
 * Mavjud shartnoma — STIR'da amaldagi shartnoma bo'lsa rad etiladi. → «Tekshirish» → raqam → hujjat → imzo → buxgalter.
 * appeal — yangi korxona murojaatidan (raqam olganda murojaat yopiladi). */
export function ContractWizard({ districts, contractId, appeal, onClose, onDone }: Props) {
  const { t, tErr } = useI18n();
  const theme = useTheme();
  const mobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [step, setStep] = useState(contractId ? -1 : 1);  // forma darhol (Excel — 0)
  const [ct, setCt] = useState<ContractItem | null>(null);
  const [customer, setCustomer] = useState<{ id: number; name: string; district_id: number } | null>(null);
  const emptyForm = (): Omit<ContractDraft, "customer_id"> => ({ requisites: EMPTY_REQ, type: "by_volume", price: null, annual_volume: null,
    annual_trips: null, valid_from: todayIso(), valid_to: yearEnd(), place: "", sign_method: "electronic", price_reason: "" });
  const [form, setForm] = useState<Omit<ContractDraft, "customer_id">>(emptyForm);
  const can = useCan();
  const errBox = useRef<HTMLDivElement>(null);
  const [checked, setChecked] = useState<ContractCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const districtName = (id?: number) => districts.find((d) => d.id === id)?.name ?? "";

  const [tariff, setTariff] = useState<number | null | undefined>(undefined);
  // Boshlang'ich tanlov: yangi shartnoma tuzish yoki mavjud (imzolangan) shartnomani kiritish (bittalab / Excel)
  const [mode, setMode] = useState<Mode>("new");
  // Mavjud shartnoma: yangi bilan bir xil forma + raqam, imzolangan sana, platforma ID, skan → buxgalter tasdig'iga
  const [ex, setEx] = useState(EMPTY_EX);
  const [exFile, setExFile] = useState<File | null>(null);
  // Bazada yo'q kontragent (STIR topilmadi): korxona birinchi «Tekshirish»da rekvizitlardan yaratiladi
  const [pendingStir, setPendingStir] = useState<string | null>(null);
  const [stirLock, setStirLock] = useState(false);  // STIR tekshirilgan — rekvizitlarda o'zgartirilmaydi
  const [stirInput, setStirInput] = useState("");
  const [conflict, setConflict] = useState<StirLookup | null>(null);  // STIR shartnomada bor — so'rov dialogi
  const [cpDistrict, setCpDistrict] = useState<number | "">(appeal?.district_id ?? (districts.length === 1 ? districts[0].id : ""));
  const exFileRef = useRef<HTMLInputElement>(null);
  // Korxonaning bazadagi nuqtasi: o'zgarmasa maqom saqlanadi, o'zgarsa — «kutilmoqda»
  const [origLoc, setOrigLoc] = useState<{ lat: number | null; lng: number | null; status?: string } | null>(null);
  const isEx = mode === "existing";
  // Qo'lda/Excel kiritilgan shartnoma (yangi yoki qaytarilgani tuzatilmoqda) — narxni legal kiritadi (ruxsat bilan), sabab majburiy
  const manualSrc = isEx || ct?.source === "manual" || ct?.source === "import";
  const vmode: Mode = ct ? (manualSrc ? "existing" : "new") : mode;
  const canPrice = can("customers.existing_price");
  const switchMode = (m: Mode) => {  // rejim almashganda forma tozalanadi
    setMode(m); setCustomer(null); setForm(emptyForm()); setEx(EMPTY_EX); setExFile(null); setChecked(null); setTariff(undefined);
    setOrigLoc(null); setPendingStir(null); setStirLock(false); setStirInput(""); setConflict(null);
    setCpDistrict(appeal?.district_id ?? (districts.length === 1 ? districts[0].id : ""));
    setStep(m === "excel" ? 0 : 1);
  };
  /** STIR bazada yo'q — rekvizitlar formasi: STIR qulflangan, nom/telefon murojaatdan (bo'lsa). */
  const startNew = (stir: string) => {
    const name = appeal && !appeal.org_name.startsWith("Yangi korxona") ? appeal.org_name : "";
    setPendingStir(stir); setStirLock(true); setCustomer(null); setOrigLoc(null); setChecked(null);
    setForm((f) => ({ ...f, place: f.place || (cpDistrict !== "" ? districtName(cpDistrict) : ""),
      sign_method: mode === "existing" ? "paper" : f.sign_method,
      requisites: { ...f.requisites, stir, name: f.requisites.name || name, phone: f.requisites.phone || (appeal?.caller_phone ?? "") } }));
  };
  /** STIR 9 raqam bo'ldi — bazadan tekshiruv (keyinchalik: my.soliq'dan rekvizitlar). */
  const onStir = async (stir: string) => {
    setBusy(true);
    try {
      const r = await contractsApi.lookup(stir);
      if (mode === "existing") {
        if (r.active_contract) { toast(t("cp_exists_active", { n: r.active_contract.number }), "error"); setStirInput(""); return; }
        if (r.customer) await pickCustomer(r.customer.id); else startNew(stir);
        return;
      }
      if (r.last_contract) { setConflict(r); return; }       // yangi shartnoma — faqat bazada yo'q kontragent
      if (r.customer) await pickCustomer(r.customer.id); else startNew(stir);  // shartnomasiz korxona (masalan, tashlab ketilgan loyiha)
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const auto = useRef(false);
  useEffect(() => {  // murojaatdan: STIR tayyor — darhol tekshiriladi
    if (!auto.current && !contractId && appeal?.stir && /^\d{9}$/.test(appeal.stir)) { auto.current = true; setStirInput(appeal.stir); onStir(appeal.stir); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const fromCustomer = (c: Partial<Requisites> & { name: string }) => ({ ...EMPTY_REQ, ...Object.fromEntries(Object.entries(c)
    .filter(([k]) => k in EMPTY_REQ).map(([k, v]) => [k, k === "is_rented" ? !!v : k === "lat" || k === "lng" || k === "geofence" ? v ?? null : v ?? ""])) } as Requisites);
  const fromContract = useCallback((c: ContractItem) => {
    setCt(c);
    if (c.customer) {
      setCustomer({ id: c.customer.id, name: c.customer.name, district_id: c.customer.district_id });
      setOrigLoc({ lat: c.customer.lat ?? null, lng: c.customer.lng ?? null, status: c.customer.location_status });
      const d = c.draft;
      const manual = c.source === "manual" || c.source === "import";
      setForm({ requisites: fromCustomer(d?.requisites ?? c.customer), type: manual ? c.type : "by_volume", price: c.price, price_reason: c.price_reason ?? "",
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
  const tariffDistrict = customer?.district_id ?? (pendingStir && cpDistrict !== "" ? cpDistrict : null);
  useEffect(() => {
    if (tariffDistrict == null || !form.valid_from) return;
    tariffsApi.price(tariffDistrict, form.valid_from).then((r) => setTariff(r.price)).catch(() => setTariff(null));
  }, [tariffDistrict, form.valid_from]);

  const pickCustomer = async (id: number) => {
    if (mode === "existing") {
      try {
        const c = await customersApi.get(id);
        setOrigLoc({ lat: c.lat, lng: c.lng, status: c.location_status }); setStirLock(!!c.stir);
        setCustomer({ id: c.id, name: c.name, district_id: c.district_id });
        setForm((f) => ({ ...f, place: f.place || districtName(c.district_id), sign_method: "paper", requisites: fromCustomer(c as unknown as Requisites) }));
        setChecked(null);
        setStep(1);
      } catch (e) { fail(e); }
      return;
    }
    try {
      const c = await customersApi.get(id);
      setOrigLoc({ lat: c.lat, lng: c.lng, status: c.location_status }); setStirLock(!!c.stir);
      const draft = await contractsApi.start(c.id, appeal?.id);  // «Tugallanmagan shartnomalar»da darhol paydo bo'ladi
      changed();
      setCt(draft);
      setCustomer({ id: c.id, name: c.name, district_id: c.district_id });
      setForm((f) => ({ ...f, place: f.place || districtName(c.district_id), requisites: fromCustomer(c as unknown as Requisites) }));
      setChecked(null);
      setStep(1);
    } catch (e) { fail(e); }
  };

  const payload = (customerId = customer!.id): ContractDraft => ({ ...form, type: manualSrc ? form.type : "by_volume", customer_id: customerId,
    price_reason: (form.price_reason ?? "").trim() || null,
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
  /** Bazada yo'q kontragent: birinchi «Tekshirish»da korxona (va yangi shartnomada — loyiha) yaratiladi. */
  const ensureCustomer = async (): Promise<{ cid: number; ctId?: number } | null> => {
    if (customer) return { cid: customer.id, ctId: ct?.id };
    const name = form.requisites.name.trim();
    if (!pendingStir) { toast(t("cp_need_stir"), "error"); return null; }
    if (name.length < 2 || cpDistrict === "") { toast(t("ex_need_name_district"), "error"); return null; }
    const c = await contractsApi.counterparty({ stir: pendingStir, name, district_id: cpDistrict, phone: form.requisites.phone || null });
    setCustomer({ id: c.id, name: c.name, district_id: c.district_id });
    setOrigLoc({ lat: null, lng: null });
    setPendingStir(null);
    let ctId: number | undefined;
    if (!isEx) {  // yangi shartnoma — loyiha darhol «Tugallanmagan»da (murojaatga bog'lanadi)
      const draft = await contractsApi.start(c.id, appeal?.id);
      setCt(draft); ctId = draft.id;
    }
    changed();
    return { cid: c.id, ctId };
  };
  const runCheck = async () => {
    setBusy(true);
    try {
      const ids = await ensureCustomer();
      if (!ids) return;
      const r = await contractsApi.check(payload(ids.cid), ids.ctId);
      setChecked(r);
      const names = [...new Set(r.errors.map((e) => errLabel(e.field)))];
      toast(r.ok ? t("ctr_check_ok") : t("ctr_check_bad_list", { n: r.errors.length, list: names.slice(0, 3).join(", ") + (names.length > 3 ? "…" : "") }),
        r.ok ? "success" : "error");
      if (!r.ok) window.setTimeout(() => errBox.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    if (isEx) {
      try {
        const c = await contractsApi.createExisting(payload());
        if (exFile) await contractsApi.uploadScan(c.id, exFile);
        changed();
        toast(t(exFile ? "ex_saved_pending" : "ex_saved_await_pdf", { n: c.display_number }), exFile ? "success" : "warning");
        onDone?.(c); onClose();
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
  const coordStatus = () => {
    const { lat, lng } = form.requisites;
    if (lat == null || lng == null) return t("coords_status_empty");
    const same = origLoc?.lat != null && origLoc.lng != null && Math.abs(origLoc.lat - lat) < 1e-6 && Math.abs(origLoc.lng - lng) < 1e-6;
    return same && origLoc?.status === "confirmed" ? t("coords_status_confirmed") : t("coords_status_pending");
  };
  function errLabel(f: string): string {
    const k = ERR_LABEL[f] ?? (`ctr_f_${f}` as MessageKey);
    return k in MESSAGES ? t(k) : f;
  }
  const focusField = (f: string) => {
    const el = document.querySelector<HTMLInputElement>(`#contract-wizard [name="${ERR_INPUT[f] ?? f}"]`);
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.focus({ preventScroll: true }); }
  };
  const priceOff = form.type === "by_volume" && form.price != null && form.price > 0 && (tariff == null || Number(form.price) !== Number(tariff));
  const setReq = (k: ReqText, v: string) => { setForm({ ...form, requisites: { ...form.requisites, [k]: v } }); setChecked(null); };
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => { setForm({ ...form, [k]: v }); setChecked(null); };
  const helper = (f: string, hint?: string) => {
    const e = errOf(f);
    return e ? t(`ce_${e.code}` as MessageKey) : hint ? t("ctr_digits", { n: hint }) : undefined;
  };

  const steps = [t("ctr_step_data"), t("ctr_step_doc")];
  return (
    <Dialog open onClose={() => !busy && close()} fullWidth maxWidth="lg" fullScreen={mobile} id="contract-wizard" data-mode={vmode}
      PaperProps={{ sx: { borderTop: 8, borderTopColor: MODE_COLOR[vmode] } }}>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1, pr: 6, color: MODE_COLOR[vmode], fontWeight: 700 }}>
        {ct?.number ? t("ctr_title_n", { n: ct.display_number }) : t(`ctr_mode_title_${vmode}` as MessageKey)}
        {ct && <StatusChip status={ct.status} />}
        <IconButton onClick={close} sx={{ position: "absolute", right: 8, top: 8 }} aria-label={t("close")}><CloseIcon /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {step >= 0 && step < 2 && <Box id="ctr-mode-banner" data-mode={vmode} sx={{ mb: 2, px: 2, py: 1.25, borderLeft: 6, borderColor: MODE_COLOR[vmode],
          borderRadius: 1, bgcolor: "action.hover" }}>
          <Typography variant="body2" color="text.secondary">{t(`ctr_mode_banner_${vmode}` as MessageKey)}</Typography>
        </Box>}
        {step >= 1 && mode !== "excel" && <Stepper activeStep={step - 1} alternativeLabel sx={{ mb: 2.5 }}>{steps.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}</Stepper>}
        {ct?.status === "returned" && ct.return_comment && <Alert severity="error" sx={{ mb: 2 }} id="ctr-returned">
          <b>{t("ctr_returned_by")}</b> {ct.return_comment}</Alert>}
        {!ct && !contractId && !customer && <Stack spacing={2} sx={{ mb: 2 }}>
          <ToggleButtonGroup exclusive fullWidth value={mode} onChange={(_, v) => { if (v && v !== mode) switchMode(v); }} id="ctr-mode"
            sx={{ flexWrap: { xs: "wrap", sm: "nowrap" } }}>
            {(["new", "existing", "excel"] as const).map((m) => <ToggleButton key={m} value={m} data-mode={m} sx={{ fontWeight: 700, borderTop: 4,
              borderTopColor: `${MODE_COLOR[m]} !important`, "&.Mui-selected, &.Mui-selected:hover": { bgcolor: MODE_COLOR[m], color: "#fff" } }}>
              {t(`ctr_mode_${m}` as MessageKey)}</ToggleButton>)}
          </ToggleButtonGroup>
          {mode === "excel" && <ExistingImport fail={fail} onDone={() => { changed(); }} />}
        </Stack>}
        {step === 1 && mode !== "excel" && <Stack spacing={2}>
          {!customer && <Stack spacing={1.5} id="cp-stir-block" sx={{ maxWidth: 640, width: "100%", alignSelf: "center", mx: "auto" }}>
            <TextField id="cp-stir" label={t("cp_stir")} value={stirInput} autoFocus disabled={busy} required
              onChange={(e) => { const v = onlyDigits(e.target.value, 9); setStirInput(v); setChecked(null);
                if (pendingStir && v !== pendingStir) { setPendingStir(null); setStirLock(false); }
                if (v.length === 9 && v !== pendingStir) onStir(v); }}
              inputProps={{ inputMode: "numeric", maxLength: 9 }} helperText={stirInput && stirInput.length < 9 ? t("ctr_digits", { n: "9" }) : " "} />
            {pendingStir && <Alert severity="info" id="cp-soliq">{t("cp_soliq_wait")}</Alert>}
            {pendingStir && <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              <TextField id="cp-name" size="small" name="name" label={t("ctr_f_name")} value={form.requisites.name} sx={{ flex: 1 }}
                onChange={(e) => setReq("name", e.target.value)} />
              <TextField id="cp-district" select size="small" label={t("district")} value={cpDistrict} sx={{ minWidth: 200 }}
                onChange={(e) => { const d = Number(e.target.value); setCpDistrict(d); setChecked(null);
                  setForm((f) => ({ ...f, place: f.place || districtName(d) })); }}>
                {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
              </TextField>
            </Stack>}
          </Stack>}
          {checked && !checked.ok && <Alert severity="error" id="ctr-errors" ref={errBox} sx={{ scrollMarginTop: 16 }}>
            <Typography fontWeight={700}>{t("ctr_errors_title", { n: checked.errors.length })}</Typography>
            <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
              {checked.errors.map((e, i) => <li key={i} data-err={e.field}>
                <Box component="button" type="button" onClick={() => focusField(e.field)} sx={{ all: "unset", cursor: "pointer", fontWeight: 600,
                  textDecoration: "underline", "&:focus-visible": { outline: 2 } }}>{errLabel(e.field)}</Box> — {t(`ce_${e.code}` as MessageKey)}</li>)}
            </Box>
          </Alert>}
          <Typography variant="subtitle2" color="text.secondary">{t("ctr_requisites")}{customer ? ` · ${districtName(customer.district_id)}` : ""}</Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
            {REQ_FIELDS.filter((f) => customer || (f.k !== "name" && f.k !== "stir")).map((f) => f.k === "cadastre"
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
              InputProps={f.k === "stir" && stirLock ? { readOnly: true } : undefined}
              sx={{ gridColumn: { md: `span ${f.span}` } }} />)}
            <CoordFields lat={form.requisites.lat} lng={form.requisites.lng} error={errOf("coords") ? helper("coords") : undefined}
              status={coordStatus()}
              onChange={(lat, lng) => { setForm((f) => ({ ...f, requisites: { ...f.requisites, lat, lng } })); setChecked(null); }} />
            <Suspense fallback={<Typography variant="caption" color="text.secondary" sx={{ gridColumn: "1 / -1" }}>…</Typography>}>
              <MapEditor value={{ lat: form.requisites.lat ?? null, lng: form.requisites.lng ?? null, geofence: form.requisites.geofence ?? null }}
                error={errOf("geofence") ? helper("geofence") : undefined}
                onChange={(v) => { setForm((f) => ({ ...f, requisites: { ...f.requisites, lat: v.lat, lng: v.lng, geofence: v.geofence } })); setChecked(null); }} />
            </Suspense>
          </Box>
          <Divider />
          <Typography variant="subtitle2" color="text.secondary">{t("ctr_terms")}</Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(4, 1fr)" } }}>
            {manualSrc
              ? <TextField select size="small" name="type" label={t("contract_type")} value={form.type} onChange={(e) => set("type", e.target.value as ContractType)}>
                {EX_TYPES.map((x) => <MenuItem key={x} value={x}>{t(`ct_${x}` as MessageKey)}</MenuItem>)}
              </TextField>
              : <TextField size="small" label={t("contract_type")} value={t("ct_by_volume")} InputProps={{ readOnly: true }} />}
            {manualSrc && (form.type !== "by_volume" || canPrice)
              ? <TextField size="small" name="price" type="number" label={`${t("ctr_price")} (${t("ctr_vat_incl")})`} value={form.price ?? ""} required
                  onChange={(e) => set("price", e.target.value === "" ? null : Number(e.target.value))} error={!!errOf("price")}
                  helperText={errOf("price") ? helper("price") : form.type === "by_volume"
                    ? (tariff ? t("ctr_tariff_ref", { p: fmtMoney(tariff) }) : tariff === null ? t("ctr_no_tariff") : "…") : undefined} />
              : <TextField size="small" name="price" label={t("ctr_price_tariff")} InputProps={{ readOnly: true }} id="ctr-tariff"
                  value={tariff ? fmtMoney(tariff) : tariff === null ? t("ctr_no_tariff") : "…"}
                  error={tariff === null || !!errOf("price")} helperText={errOf("price") ? helper("price") : t("ctr_tariff_hint")} />}
            {manualSrc && canPrice && priceOff && <TextField size="small" name="price_reason" required label={t("ctr_price_reason")}
              value={form.price_reason ?? ""} onChange={(e) => set("price_reason", e.target.value)} placeholder={t("ctr_price_reason_ph")}
              error={!!errOf("price_reason")} helperText={errOf("price_reason") ? helper("price_reason") : t("ctr_price_reason_hint")}
              sx={{ gridColumn: { md: "span 2" } }} inputProps={{ maxLength: 255 }} />}
            <TextField size="small" name="annual_volume" type="number" label={t("ctr_annual_volume")} value={form.annual_volume ?? ""}
              onChange={(e) => set("annual_volume", e.target.value === "" ? null : Number(e.target.value))}
              error={!!errOf("annual_volume")} helperText={helper("annual_volume")} />
            <TextField size="small" name="place" label={t("ctr_place")} value={form.place} onChange={(e) => set("place", e.target.value)}
              error={!!errOf("place")} helperText={helper("place")} />
            {manualSrc || ct?.number
              ? <TextField size="small" name="valid_from" type="date" label={t("valid_from")} value={form.valid_from} InputLabelProps={{ shrink: true }}
                onChange={(e) => set("valid_from", e.target.value)} error={!!errOf("valid_from")} helperText={helper("valid_from")} />
              : <TextField size="small" name="valid_from" type="date" label={t("valid_from")} value={todayIso()} InputLabelProps={{ shrink: true }}
                InputProps={{ readOnly: true }} helperText={t("ctr_start_today")} />}
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
              <Box sx={{ gridColumn: { md: "1 / -1" } }}>
                <input ref={exFileRef} type="file" hidden accept="application/pdf" id="ex-file" onChange={(e) => setExFile(e.target.files?.[0] ?? null)} />
                <Button size="small" variant={exFile ? "text" : "outlined"} color={exFile ? "primary" : "warning"} onClick={() => exFileRef.current?.click()}>
                  {t("ex_pdf_required")}</Button>
                {exFile ? <Chip size="small" color="success" label={exFile.name} onDelete={() => setExFile(null)} sx={{ ml: 1 }} />
                  : <Typography variant="caption" color="warning.main" sx={{ ml: 1 }}>{t("ex_pdf_hint")}</Typography>}
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
        {conflict && <RequestDialog lookup={conflict} stir={stirInput} fail={fail}
          onCancel={() => { setConflict(null); setStirInput(""); }}
          onSent={() => { setConflict(null); changed(); onClose(); }} />}
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
            sx={{ bgcolor: MODE_COLOR[vmode], "&:hover": { bgcolor: MODE_HOVER[vmode] } }}>{t(isEx ? (exFile ? "ex_send_accountant" : "ex_save_await_pdf") : ct ? "ctr_save_changes" : "ctr_save_number")}</Button>
        </>}
      </DialogActions>
    </Dialog>
  );
}

/** STIR bazadagi shartnomada bor: yangi shartnoma o'rniga so'rov — qo'shimcha shartnoma (buxgalterga), yangi filial yoki
 * manzilni o'zgartirish (GPS'ga). «Bekor qilish» — forma qaytadi, STIR tozalanadi. */
function RequestDialog({ lookup, stir, fail, onCancel, onSent }: { lookup: StirLookup; stir: string; fail: (e: unknown) => void;
  onCancel: () => void; onSent: () => void }) {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const c = lookup.last_contract!;
  const send = async (kind: "amendment" | "branch" | "address") => {
    setBusy(true);
    try { await contractsApi.request({ stir, kind, note: note.trim() || null }); toast(t(`cr_sent_${kind}` as MessageKey), "success"); onSent(); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <Dialog open onClose={() => !busy && onCancel()} maxWidth="sm" fullWidth id="cp-request-dialog">
      <DialogTitle sx={{ fontWeight: 700 }}>{t("cr_title")}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Typography>{t("cr_text", { name: lookup.customer?.name ?? "", number: c.number, to: c.valid_to })}</Typography>
          <TextField size="small" label={`${t("cr_note")} (${t("ctr_optional_short")})`} value={note} onChange={(e) => setNote(e.target.value)}
            inputProps={{ maxLength: 500 }} />
          <Stack spacing={1}>
            <Button id="cr-amendment" variant="contained" disableElevation disabled={busy} onClick={() => send("amendment")}>{t("cr_amendment")}</Button>
            <Button id="cr-branch" variant="outlined" disabled={busy} onClick={() => send("branch")}>{t("cr_branch")}</Button>
            <Button id="cr-address" variant="outlined" disabled={busy} onClick={() => send("address")}>{t("cr_address")}</Button>
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions><Button id="cr-cancel" onClick={onCancel} disabled={busy}>{t("cancel")}</Button></DialogActions>
    </Dialog>
  );
}

const DELETE_MIN = 5;
/** Tugallanmagan shartnomani o'chirish: izoh majburiy (kamida 5 belgi) — Vaziyat paneliga matni bilan tushadi. */
export function DeleteContractDialog({ ct, onClose, onDeleted }: { ct: ContractItem; onClose: () => void; onDeleted: () => void }) {
  const { t, tErr } = useI18n();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const ok = reason.trim().length >= DELETE_MIN;
  const go = async () => {
    if (!ok) return;
    setBusy(true);
    try { await contractsApi.remove(ct.id, reason.trim()); changed(); toast(t("ctr_deleted"), "success"); onDeleted(); }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); } finally { setBusy(false); }
  };
  return (
    <Dialog open onClose={() => !busy && onClose()} fullWidth maxWidth="sm" id="ctr-delete-dialog">
      <DialogTitle sx={{ color: "error.main", fontWeight: 700 }}>{t("ctr_delete_title")}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Typography>{t("ctr_delete_what", { n: ct.display_number || t("ctr_no_number"), c: ct.customer?.name ?? "" })}</Typography>
          <Alert severity="warning" variant="outlined">{t("ctr_delete_hint")}</Alert>
          <TextField id="ctr-delete-reason" autoFocus multiline minRows={2} required label={t("ctr_delete_reason")} value={reason}
            onChange={(e) => setReason(e.target.value)} inputProps={{ maxLength: 500 }} error={reason.length > 0 && !ok}
            helperText={ok ? t("ctr_delete_reason_hint") : t("ctr_delete_reason_min", { n: DELETE_MIN })} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>{t("cancel")}</Button>
        <Button id="ctr-delete-confirm" color="error" variant="contained" disableElevation disabled={!ok || busy} onClick={go}>{t("ctr_delete_do")}</Button>
      </DialogActions>
    </Dialog>
  );
}

function DocStep({ ct, busy, setBusy, fail, onSigned, onDeleted }: { ct: ContractItem; busy: boolean; setBusy: (b: boolean) => void;
  fail: (e: unknown) => void; onSigned: (c: ContractItem) => void; onDeleted: () => void }) {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [sign, setSign] = useState({ signed_on: todayIso(), sign_method: ct.sign_method ?? "electronic" });
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
      onSigned(await contractsApi.sign(ct.id, { sign_method: sign.sign_method, signed_on: electronic ? undefined : sign.signed_on,
        file: electronic ? null : file }));
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const [askDelete, setAskDelete] = useState(false);
  const remove = () => setAskDelete(true);
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
        <Alert severity="info" variant="outlined">{t(sign.sign_method === "paper" ? "ctr_hint_paper" : "ctr_hint_electronic")}</Alert>
        {canSign && <Paper variant="outlined" sx={{ p: 2 }} id="ctr-sign">
          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("ctr_sign_title")}</Typography>
          <Stack spacing={1.5}>
            <RadioGroup row value={sign.sign_method} onChange={(e) => setSign({ ...sign, sign_method: e.target.value as "electronic" | "paper" })}>
              <FormControlLabel value="electronic" control={<Radio size="small" />} label={t("ctr_m_electronic")} />
              <FormControlLabel value="paper" control={<Radio size="small" />} label={t("ctr_m_paper")} />
            </RadioGroup>
            {!electronic && <TextField size="small" type="date" name="signed_on" label={t("signed_on")} value={sign.signed_on} InputLabelProps={{ shrink: true }}
              inputProps={{ max: todayIso() }} onChange={(e) => setSign({ ...sign, signed_on: e.target.value })} />}
            {!electronic && <Box>
              <input ref={fileRef} type="file" hidden accept="application/pdf" id="ctr-file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <Button size="small" variant={!file ? "outlined" : "text"} color={!file ? "warning" : "primary"}
                onClick={() => fileRef.current?.click()}>{t("ctr_attach_scan_required")}</Button>
              {file && <Chip size="small" color="success" label={file.name} onDelete={() => setFile(null)} sx={{ ml: 1 }} />}
              {!file && <Typography variant="caption" color="warning.main" display="block" sx={{ mt: 0.5 }}>{t("ctr_paper_wait_hint")}</Typography>}
            </Box>}
            <Button id="ctr-signed" variant="contained" disableElevation size="large" startIcon={<DrawIcon />}
              disabled={busy || (!electronic && (!sign.signed_on || (!file && !ct.has_scan)))} onClick={submit}
              sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("ctr_signed_send")}</Button>
          </Stack>
        </Paper>}
        {ct.status === "draft" && <Button color="error" onClick={remove} disabled={busy} id="ctr-delete">{t("ctr_delete")}</Button>}
        {askDelete && <DeleteContractDialog ct={ct} onClose={() => setAskDelete(false)} onDeleted={() => { setAskDelete(false); onDeleted(); }} />}
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
