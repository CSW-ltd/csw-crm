import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, List, ListItemButton, ListItemText, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { adminApi, appealsApi, customersApi, requestsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { StageChip } from "@/components/Stage";
import type { MessageKey } from "@/i18n/messages";
import { confirmDialog, toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import { getSocket } from "@/lib/socket";
import type { Appeal, CustomerListItem, District, RequestItem, WasteType } from "@/types";
import { WASTE_TYPES } from "./OrderFields";
import AddBusinessIcon from "@mui/icons-material/AddBusiness";
import { useAppSelector } from "@/store";

/** Telefonning oxirgi 9 raqami (998 kodisiz) */
const phoneDigits = (v: string) => { const d = v.replace(/\D/g, ""); return d.length >= 12 && d.startsWith("998") ? d.slice(3) : d; };

/** Status chipi rangi */
export const STATUS_COLOR: Record<string, "default" | "info" | "success" | "warning" | "error"> = {
  new: "info", printing: "warning", assigned: "info", enroute: "info", onsite: "info", done: "success", suspect: "warning", failed: "error", cancelled: "default",
};

export function RequestChips({ r }: { r: Pick<RequestItem, "is_repeat" | "overdue" | "waste_type"> }) {
  const { t } = useI18n();
  return <>
    {r.is_repeat && <Chip size="small" color="secondary" variant="outlined" label={t("repeat")} />}
    {r.overdue && <Chip size="small" color="error" label={t("overdue")} />}
    {r.waste_type === "septic" && <Chip size="small" color="info" label={t("w_septic")} />}
  </>;
}

/**
 * Call-center operatori: qo'ng'iroq → korxonani maxsus raqam bo'yicha topish → murojaat (telefon, chiqindi turi, kutib oluvchi)
 * yoki «Yangi korxona» (telefon, STIR, kutib oluvchi) — maxsus raqam SMS bilan korxonaga, murojaat yuridik bo'limga.
 */
export function OperatorHome() {
  const { t, tErr } = useI18n();
  const me = useAppSelector((s) => s.auth.user);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<CustomerListItem[]>([]);
  const [picked, setPicked] = useState<CustomerListItem | null>(null);
  const [newMode, setNewMode] = useState(false);
  const [order, setOrder] = useState({ caller_phone: "", caller_name: "", waste_type: "household" as WasteType });
  const [nc, setNc] = useState({ phone: "", stir: "", contact_name: "", district_id: "" as number | "" });
  const [taken, setTaken] = useState<{ customer_id: number; name: string } | null>(null);
  const [districts, setDistricts] = useState<District[]>([]);
  const [mine, setMine] = useState<RequestItem[]>([]);
  const [appeals, setAppeals] = useState<Appeal[]>([]);
  const [busy, setBusy] = useState(false);
  const myDistricts = districts.filter((d) => d.is_active && (me?.district_ids ?? []).includes(d.id));

  const loadMine = useCallback(async () => {
    const [r, a] = await Promise.all([requestsApi.list({ mine: true, limit: 30 }), appealsApi.list({ mine: true })]);
    setMine(r.items); setAppeals(a);
  }, []);
  useEffect(() => {
    adminApi.districts().then(setDistricts).catch(() => undefined);
    loadMine().catch(() => undefined);
    const s = getSocket();
    const on = () => { loadMine().catch(() => undefined); };
    s.on("request:updated", on); s.on("appeal:updated", on);
    return () => { s.off("request:updated", on); s.off("appeal:updated", on); };
  }, [loadMine]);

  // Qidiruv: maxsus raqam (KTR47), nom yoki telefon; yozish to'xtagach 300 ms
  useEffect(() => {
    if (q.trim().length < 2) { setFound([]); return; }
    const h = setTimeout(() => customersApi.search({ q: q.trim(), limit: 8 }).then((r) => setFound(r.items)).catch(() => setFound([])), 300);
    return () => clearTimeout(h);
  }, [q]);

  const reset = () => { setPicked(null); setNewMode(false); setOrder({ caller_phone: "", caller_name: "", waste_type: "household" }); setQ("");
    setFound([]); setNc({ phone: "", stir: "", contact_name: "", district_id: "" }); setTaken(null); };
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");

  const pick = (c: CustomerListItem) => { setPicked(c); setOrder((o) => ({ ...o, caller_phone: c.phone ?? "" })); };
  const submitRequest = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      let confirm_repeat = false;
      const open = await requestsApi.openFor(picked.id);
      if (open.length) {
        const list = open.map((r) => `${r.number} (${t(`s_${r.status}` as MessageKey)})`).join(", ");
        if (!(await confirmDialog(t("repeat_title"), t("repeat_confirm"), t("cancel"), t("repeat_text", { list }), false))) return;
        confirm_repeat = true;
      }
      const r = await requestsApi.create({ customer_id: picked.id, waste_type: order.waste_type, caller_phone: order.caller_phone.trim() || null,
        caller_name: order.caller_name.trim() || null, source: "phone", volume_estimate: null, preferred_time: null, note: null, confirm_repeat });
      toast(t("request_opened", { n: r.number ?? "" }));
      reset();
      loadMine();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  const submitNew = async () => {
    setBusy(true); setTaken(null);
    try {
      const district_id = nc.district_id === "" ? (myDistricts.length === 1 ? myDistricts[0].id : null) : nc.district_id;
      const a = await appealsApi.newCompany({ phone: nc.phone, stir: nc.stir, contact_name: nc.contact_name.trim(), district_id });
      toast(t("nc_sent", { n: a.number ?? "" }));
      reset();
      loadMine();
    } catch (e) {
      if (errorCode(e) === "stir_taken") {
        const d = (e as { response?: { data?: { error?: { details?: { customer_id: number; name: string } } } } }).response?.data?.error?.details;
        if (d) setTaken(d);
      }
      fail(e);
    } finally { setBusy(false); }
  };
  const useTaken = async () => {
    if (!taken) return;
    try { const c = await customersApi.get(taken.customer_id); setNewMode(false); pick(c); setOrder((o) => ({ ...o, caller_phone: nc.phone, caller_name: nc.contact_name })); }
    catch (e) { fail(e); }
  };

  const dName = (id: number) => districts.find((d) => d.id === id)?.name ?? "";
  const ncValid = phoneDigits(nc.phone).length === 9 && /^\d{9}$/.test(nc.stir) && nc.contact_name.trim().length >= 2
    && (myDistricts.length <= 1 || nc.district_id !== "");

  return (
    <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "minmax(0, 3fr) minmax(0, 2fr)" }, alignItems: "start" }}>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}>
          <Typography variant="h5">{t("operator_title")}</Typography>
          <Button id="op-new-company" variant="contained" disableElevation startIcon={<AddBusinessIcon />} onClick={() => { reset(); setNewMode(true); }}
            sx={{ bgcolor: "#1f8a4c", "&:hover": { bgcolor: "#17703d" } }}>{t("nc_button")}</Button>
        </Stack>
        <Paper variant="outlined" sx={{ p: 2 }}>
          {!picked && !newMode && <>
            <TextField id="op-search" fullWidth autoFocus label={t("find_customer")} helperText={t("find_customer_hint")} value={q}
              onChange={(e) => setQ(e.target.value)} />
            {found.length > 0 && <List dense sx={{ mt: 1, border: 1, borderColor: "divider", borderRadius: 1 }}>
              {found.map((c) => (
                <ListItemButton key={c.id} onClick={() => pick(c)} data-customer={c.code ?? c.fixed_no}>
                  <ListItemText primary={<><b style={{ fontFamily: "ui-monospace, monospace" }}>{c.code}</b> · {c.name}</>}
                    secondary={[dName(c.district_id), c.address, c.phone].filter(Boolean).join(" · ")} />
                  {c.missing_fields.length > 0 && <Chip size="small" color="error" variant="outlined" label={t("missing_contract")} />}
                </ListItemButton>
              ))}
            </List>}
            {q.trim().length >= 2 && !found.length && <Alert severity="info" sx={{ mt: 1.5 }}>{t("op_not_found_hint")}</Alert>}
          </>}

          {picked && <Stack spacing={2}>
            <Typography variant="h6">{t("new_request_for", { name: picked.name })}</Typography>
            <Typography variant="body2" color="text.secondary">{[picked.code, dName(picked.district_id), picked.address].filter(Boolean).join(" · ")}</Typography>
            {picked.missing_fields.length > 0 && <Alert severity="warning">{t("op_no_contract_hint")}</Alert>}
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <TextField id="op-phone" size="small" label={t("phone")} value={order.caller_phone} onChange={(e) => setOrder({ ...order, caller_phone: e.target.value })} />
              <TextField id="op-waste" size="small" select label={t("waste_type")} value={order.waste_type}
                onChange={(e) => setOrder({ ...order, waste_type: e.target.value as WasteType })}>
                {WASTE_TYPES.map((w) => <MenuItem key={w} value={w}>{t(`wt_${w}` as MessageKey)}</MenuItem>)}
              </TextField>
              <TextField id="op-contact" size="small" label={t("receiver_name")} value={order.caller_name}
                onChange={(e) => setOrder({ ...order, caller_name: e.target.value })} sx={{ gridColumn: { sm: "1 / -1" } }} />
            </Box>
            <Stack direction="row" spacing={1}>
              <Button id="op-submit" variant="contained" disableElevation disabled={busy || order.caller_name.trim().length < 2} onClick={submitRequest}>
                {t("create_murojaat")}</Button>
              <Button onClick={reset}>{t("cancel")}</Button>
            </Stack>
          </Stack>}

          {newMode && <Stack spacing={2}>
            <Typography variant="h6">{t("nc_title")}</Typography>
            <Typography variant="body2" color="text.secondary">{t("nc_hint")}</Typography>
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <TextField id="nc-phone" size="small" label={t("phone")} value={nc.phone} onChange={(e) => setNc({ ...nc, phone: e.target.value })}
                placeholder="94 512 11 16" />
              <TextField id="nc-stir" size="small" label={t("stir")} value={nc.stir} onChange={(e) => { setNc({ ...nc, stir: e.target.value.replace(/\D/g, "").slice(0, 9) }); setTaken(null); }}
                slotProps={{ htmlInput: { inputMode: "numeric", maxLength: 9 } }} error={!!taken} />
              <TextField id="nc-contact" size="small" label={t("receiver_name")} value={nc.contact_name}
                onChange={(e) => setNc({ ...nc, contact_name: e.target.value })} sx={{ gridColumn: { sm: "1 / -1" } }} />
              {myDistricts.length > 1 && <TextField id="nc-district" size="small" select label={t("district")} value={nc.district_id}
                onChange={(e) => setNc({ ...nc, district_id: Number(e.target.value) })} sx={{ gridColumn: { sm: "1 / -1" } }}>
                {myDistricts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
              </TextField>}
            </Box>
            {taken && <Alert severity="error" id="nc-taken" action={<Button color="inherit" size="small" onClick={useTaken}>{t("nc_use_taken")}</Button>}>
              {t("nc_stir_taken", { name: taken.name })}</Alert>}
            <Stack direction="row" spacing={1}>
              <Button id="nc-submit" variant="contained" disableElevation disabled={busy || !ncValid} onClick={submitNew}
                sx={{ bgcolor: "#1f8a4c", "&:hover": { bgcolor: "#17703d" } }}>{t("nc_submit")}</Button>
              <Button onClick={reset}>{t("cancel")}</Button>
            </Stack>
          </Stack>}
        </Paper>
      </Stack>

      <Stack spacing={2}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>{t("my_requests_today")}</Typography>
          {!mine.length && <Typography color="text.secondary">—</Typography>}
          <Stack spacing={1} id="op-my-requests">
            {mine.map((r) => (
              <Box key={r.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 1.25 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography fontWeight={600} sx={{ fontVariantNumeric: "tabular-nums" }}>{r.number}</Typography>
                  <StageChip stage={r.stage} />
                  <Chip size="small" variant="outlined" color={STATUS_COLOR[r.status]} label={t(`s_${r.status}` as MessageKey)} />
                  <RequestChips r={r} />
                </Stack>
                <Typography variant="body2">{r.customer.name}</Typography>
                <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                  <Typography variant="caption" color="text.secondary">
                    {formatDateTime(new Date(r.created_at + "Z"))}{r.due_at && `, ${t("due_at")}: ${formatDateTime(new Date(r.due_at + "Z"))}`}
                  </Typography>
                </Stack>
              </Box>
            ))}
          </Stack>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>{t("my_appeals")}</Typography>
          {!appeals.length && <Typography color="text.secondary">—</Typography>}
          <Stack spacing={1} id="op-my-appeals">
            {appeals.map((a) => (
              <Box key={a.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 1.25 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography fontWeight={600}>{a.number}</Typography>
                  <Chip size="small" color={a.status === "accepted" ? "success" : a.status === "rejected" ? "default" : "warning"}
                    label={t(`ap_${a.status}` as MessageKey)} />
                </Stack>
                <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                  <Typography variant="body2">{a.org_name}</Typography>
                </Stack>
                {a.reject_reason && <Typography variant="caption" color="error">{a.reject_reason}</Typography>}
              </Box>
            ))}
          </Stack>
        </Paper>
      </Stack>
    </Box>
  );
}
