import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Badge, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, InputAdornment, Radio,
  RadioGroup, Stack, Step, StepLabel, Stepper, Tab, Tabs, TextField, Typography } from "@mui/material";
import AttachIcon from "@mui/icons-material/AttachFile";
import DescriptionIcon from "@mui/icons-material/DescriptionOutlined";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import SearchIcon from "@mui/icons-material/Search";
import TaskIcon from "@mui/icons-material/TaskAlt";
import { customersApi, ordersApi, requestsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { PaperSheet } from "@/components/OrderPaper";
import { SoundToggle, useAlertSound, useNewItemsSignal, useNow } from "@/components/Stage";
import { GreenCard, YellowCard } from "@/components/StageCards";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { getSocket } from "@/lib/socket";
import type { CustomerDetail, OrderPaper, RequestItem } from "@/types";
import { AppealsTab } from "./AppealsTab";
import { MurojaatBoard } from "./MurojaatBoard";
import { useAppSelector } from "@/store";
import type { RefData } from "./AdminHome";
import { usePersisted } from "@/hooks/usePersisted";

type Sub = "board" | "yellow" | "green" | "appeals";

/**
 * Murojaatlar (legal): «Jarayonda» — sariq kartalar (mashina biriktirilgan, varaqa qaytishi kutilmoqda),
 * «Bajarilganlar» — yashil, «Birinchi murojaatlar» — bazada yo'q korxonalar.
 * Sariq kartani yopish: skan → maxfiy kod → kub va tur → yashil.
 */
export function OrdersTab(ref: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const now = useNow();
  const sound = useAlertSound();
  const role = useAppSelector((st) => st.auth.user?.role);
  // Admin/manager — barcha murojaatlar bitta ro'yxatda (4 rang); legal — Jarayonda / Bajarilganlar
  const board = role === "admin" || role === "manager";
  const subs: Sub[] = [...(board && can("requests.view") ? ["board" as Sub] : []),
    ...(!board && (can("orders.view") || can("requests.view")) ? ["yellow", "green"] as Sub[] : []), ...(can("appeals.view") ? ["appeals" as Sub] : [])];
  const [sub, setSub] = usePersisted<Sub>("orders.sub", subs[0] ?? "yellow");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [yellow, setYellow] = useState<RequestItem[]>([]);
  const [green, setGreen] = useState<RequestItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [closing, setClosing] = useState<RequestItem | null>(null);
  const [contractOf, setContractOf] = useState<number | null>(null);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);

  useEffect(() => { const h = window.setTimeout(() => setQuery(q.trim()), 300); return () => window.clearTimeout(h); }, [q]);
  const load = useCallback(async () => {
    if (!subs.includes("yellow")) return;
    try {
      const [y, g] = await Promise.all([requestsApi.list({ stage: "yellow", q: query || undefined, limit: 200 }),
        requestsApi.list({ stage: "green", q: query || undefined, limit: 50 })]);
      setYellow(y.items); setGreen(g.items); setLoaded(true);
    } catch (e) { fail(e); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, fail]);
  useEffect(() => {
    load();
    const s = getSocket();
    s.on("request:updated", load);
    return () => { s.off("request:updated", load); };
  }, [load]);
  // Yangi sariq karta (mashina biriktirildi) — ovozli alert; qidiruv paytida emas
  useNewItemsSignal(query ? [] : yellow.map((r) => r.id), loaded && !query, () => sound.play("yellow"));

  const unlock = async (r: RequestItem) => {
    try { await ordersApi.unlock(r.order_form!.id); toast(t("of_unlocked")); load(); } catch (e) { fail(e); }
  };

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <Tabs value={sub} onChange={(_, v) => setSub(v)} sx={{ flex: 1 }}>
          {subs.includes("board") && <Tab value="board" id="ord-tab-board" label={t("ord_board")} />}
          {subs.includes("yellow") && <Tab value="yellow" id="ord-tab-yellow"
            label={<Badge color="warning" badgeContent={yellow.length} sx={{ pr: 1.5 }}>{t("ord_yellow")}</Badge>} />}
          {subs.includes("green") && <Tab value="green" id="ord-tab-green" label={t("ord_green")} />}
          {subs.includes("appeals") && <Tab value="appeals" id="ord-tab-appeals" label={t("ord_appeals")} />}
        </Tabs>
        {(sub === "yellow" || sub === "green") && <TextField id="ord-search" size="small" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ord_search")}
          sx={{ minWidth: 300 }} InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> }} />}
        {sub === "yellow" && <SoundToggle on={sound.on} toggle={sound.toggle} />}
      </Stack>

      {sub === "yellow" && <Box id="ord-yellow" sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        {loaded && !yellow.length && <Typography color="text.secondary">{t(query ? "ord_not_found" : "ord_no_yellow")}</Typography>}
        {yellow.map((r) => (
          <YellowCard key={r.id} r={r} now={now}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {can("orders.close") && r.order_form && <Button data-close={r.id} variant="contained" disableElevation startIcon={<TaskIcon />}
                disabled={!r.order_form.printed || r.order_form.locked} onClick={() => setClosing(r)}
                sx={{ bgcolor: "#1f8a4c", "&:hover": { bgcolor: "#17703d" } }}>{t("ord_close")}</Button>}
              <Button size="small" variant="outlined" color="inherit" startIcon={<DescriptionIcon />} onClick={() => setContractOf(r.customer.id)}>
                {t("ord_contract")}</Button>
              {r.order_form?.locked && can("orders.unlock") && <Button size="small" color="error" startIcon={<LockOpenIcon />}
                onClick={() => unlock(r)}>{t("of_unlock")}</Button>}
            </Stack>
            {r.order_form && !r.order_form.printed && <Typography variant="caption" sx={{ display: "block", mt: 0.75 }}>{t("ord_wait_print")}</Typography>}
          </YellowCard>
        ))}
      </Box>}

      {sub === "green" && <Stack spacing={1} id="ord-green">
        {loaded && !green.length && <Typography color="text.secondary">{t("ord_no_green")}</Typography>}
        {green.map((r) => <GreenCard key={r.id} r={r}></GreenCard>)}
      </Stack>}

      {sub === "board" && <MurojaatBoard {...ref} />}
      {sub === "appeals" && <AppealsTab {...ref} />}
      {closing && <CloseDialog r={closing} onClose={() => setClosing(null)} onDone={() => { setClosing(null); load(); }} />}
      {contractOf && <ContractDialog customerId={contractOf} onClose={() => setContractOf(null)} />}
    </Stack>
  );
}

function ContractDialog({ customerId, onClose }: { customerId: number; onClose: () => void }) {
  const { t, tErr } = useI18n();
  const [c, setC] = useState<CustomerDetail | null>(null);
  useEffect(() => { customersApi.get(customerId).then(setC).catch((e) => { toast(tErr(errorCode(e), errorMessage(e)), "error"); onClose(); }); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [customerId]);
  const today = new Date().toISOString().slice(0, 10);
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{c ? `${c.name} · ${c.code ?? ""}` : t("ord_contract")}</DialogTitle>
      <DialogContent dividers id="contract-dialog">
        {!c ? <CircularProgress size={24} /> : !c.contracts.length ? <Alert severity="warning">{t("ord_no_contract")}</Alert>
          : <Stack spacing={1}>{[...c.contracts].reverse().map((k) => {
            const active = k.is_active && k.valid_from <= today && today <= k.valid_to;
            return (
              <Box key={k.id} sx={{ border: 1, borderColor: active ? "success.main" : "divider", borderRadius: 1, p: 1.25 }}>
                <Typography fontWeight={700}>{k.number} {active && <Typography component="span" color="success.main" variant="body2">· {t("active")}</Typography>}</Typography>
                <Typography variant="body2">{t(`ct_${k.type}` as MessageKey)} · {k.price ? `${Number(k.price).toLocaleString("ru-RU")} so'm` : "—"}</Typography>
                <Typography variant="body2" color="text.secondary">{k.valid_from} — {k.valid_to}{k.signed_on && ` · ${t("signed_on")}: ${k.signed_on}`}</Typography>
              </Box>
            );
          })}</Stack>}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>{t("close")}</Button></DialogActions>
    </Dialog>
  );
}

/** Yopish: 1) skan, 2) maxfiy kod (3 urinish), 3) avtomatik to'lgan forma + kub va tur → «Murojaatni yopish». */
function CloseDialog({ r, onClose, onDone }: { r: RequestItem; onClose: () => void; onDone: () => void }) {
  const { t, tErr } = useI18n();
  const form = r.order_form!;
  const [step, setStep] = useState(form.has_scan ? (form.verified ? 2 : 1) : 0);
  const [file, setFile] = useState<File | null>(null);
  const [code, setCode] = useState("");
  const [left, setLeft] = useState(form.attempts_left);
  const [locked, setLocked] = useState(form.locked);
  const [paper, setPaper] = useState<OrderPaper | null>(null);
  const [volume, setVolume] = useState("");
  const [kind, setKind] = useState<"solid" | "liquid" | "">("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");

  useEffect(() => { if (step === 2 && !paper) ordersApi.paper(form.id).then(setPaper).catch(fail); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [step]);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try { await ordersApi.uploadScan(form.id, file); setStep(1); } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const verify = async () => {
    setBusy(true);
    try { setPaper(await ordersApi.verify(form.id, code)); setStep(2); }
    catch (e) {
      const c = errorCode(e);
      if (c === "order_locked") setLocked(true);
      const d = (e as { response?: { data?: { error?: { details?: { attempts_left?: number } } } } }).response?.data?.error?.details;
      if (d?.attempts_left !== undefined) setLeft(d.attempts_left);
      fail(e);
    } finally { setBusy(false); }
  };
  const vol = Number(volume.replace(",", "."));
  const ready = vol > 0 && !!kind;
  const close = async () => {
    if (!ready) return;
    setBusy(true);
    try { await ordersApi.close(form.id, vol, kind as "solid" | "liquid"); toast(t("ord_closed_ok", { n: r.number ?? "" })); onDone(); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    // Kod tasdiqlangach: kub va chiqindi turi kiritilmaguncha forma umuman yopilmaydi (Esc, tashqariga bosish, tugma yo'q)
    <Dialog open disableEscapeKeyDown={step === 2 && !ready}
      onClose={() => { if (step < 2 || ready) onClose(); else toast(t("ord_fill_first"), "warning"); }} maxWidth="lg" fullWidth>
      <DialogTitle>{t("ord_close_title")} · {r.customer.name}</DialogTitle>
      <DialogContent dividers id="close-dialog">
        <Stepper activeStep={step} sx={{ mb: 3 }}>
          {["ord_step_scan", "ord_step_code", "ord_step_form"].map((k) => <Step key={k}><StepLabel>{t(k as MessageKey)}</StepLabel></Step>)}
        </Stepper>
        {step === 0 && <Stack spacing={2} alignItems="flex-start">
          <Typography>{t("ord_scan_hint")}</Typography>
          <input ref={input} id="scan-input" type="file" accept="image/jpeg,image/png,application/pdf" hidden
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button variant="outlined" startIcon={<AttachIcon />} onClick={() => input.current?.click()}>{file ? file.name : t("ord_pick_scan")}</Button>
        </Stack>}
        {step === 1 && <Stack spacing={2} sx={{ maxWidth: 420 }}>
          {locked ? <Alert severity="error" id="code-locked">{t("ord_locked")}</Alert> : <>
            <Typography>{t("ord_code_hint")}</Typography>
            <TextField id="code-input" autoFocus label={t("of_code_label")} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())}
              inputProps={{ maxLength: 12, style: { fontFamily: "ui-monospace, monospace", fontSize: 22, letterSpacing: 4 }, autoComplete: "off" }}
              helperText={t("ord_attempts_left", { n: left })} error={left < 3}
              onKeyDown={(e) => { if (e.key === "Enter" && code.length >= 4) verify(); }} />
          </>}
        </Stack>}
        {step === 2 && <Stack spacing={2}>
          {!paper ? <CircularProgress size={24} /> : <PaperSheet p={paper} autofill={{ volume, kind: kind || null }} />}
          <Stack direction={{ xs: "column", md: "row" }} spacing={3} alignItems={{ md: "center" }}>
            <TextField id="volume-input" label={t("ord_volume")} value={volume} onChange={(e) => setVolume(e.target.value.replace(/[^\d.,]/g, ""))}
              required error={!!volume && !(vol > 0)} InputProps={{ endAdornment: <InputAdornment position="end">m³</InputAdornment> }}
              sx={{ maxWidth: 220 }} />
            <RadioGroup row value={kind} onChange={(e) => setKind(e.target.value as "solid" | "liquid")} id="kind-input">
              <FormControlLabel value="solid" control={<Radio />} label={t("of_solid")} />
              <FormControlLabel value="liquid" control={<Radio />} label={t("of_liquid")} />
            </RadioGroup>
          </Stack>
          {!ready && <Alert severity="info">{t("ord_fill_first")}</Alert>}
        </Stack>}
      </DialogContent>
      <DialogActions>
        {(step < 2 || ready) && <Button onClick={onClose}>{t("cancel")}</Button>}
        {step === 0 && <Button id="scan-upload" variant="contained" disableElevation disabled={!file || busy} onClick={upload}>{t("ord_upload")}</Button>}
        {step === 1 && !locked && <Button id="code-verify" variant="contained" disableElevation disabled={code.length < 4 || busy} onClick={verify}>
          {t("ord_verify")}</Button>}
        {step === 2 && ready && <Button id="order-close" variant="contained" disableElevation disabled={busy} onClick={close}
          sx={{ bgcolor: "#1f8a4c", "&:hover": { bgcolor: "#17703d" } }}>{t("ord_close_request")}</Button>}
      </DialogActions>
    </Dialog>
  );
}
