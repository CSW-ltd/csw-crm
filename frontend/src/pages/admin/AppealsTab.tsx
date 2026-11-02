import { useCallback, useEffect, useState } from "react";
import { Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Paper, Stack, TextField,
  Typography } from "@mui/material";
import { appealsApi, type ContractCreate } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import { getSocket } from "@/lib/socket";
import type { Appeal, ContractType } from "@/types";
import { districtLabel, type RefData } from "./AdminHome";
import { usePersisted } from "@/hooks/usePersisted";

const CONTRACT_TYPES: ContractType[] = ["per_trip", "by_volume", "monthly", "one_off"];
const today = () => new Date().toISOString().slice(0, 10);

/** Birinchi murojaatlar navbati: yurist korxona kartasini (va shartnomani) ochadi — ariza avtomatik GPS xodimiga o'tadi. */
export function AppealsTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [status, setStatus] = usePersisted<"new" | "accepted" | "rejected" | "">("appeals.status", "new");
  const [items, setItems] = useState<Appeal[]>([]);
  const [open, setOpen] = useState<Appeal | null>(null);

  const load = useCallback(async () => setItems(await appealsApi.list({ status: status || undefined })), [status]);
  useEffect(() => {
    load().catch(() => undefined);
    const s = getSocket();
    const on = () => { load().catch(() => undefined); };
    s.on("appeal:updated", on);
    return () => { s.off("appeal:updated", on); };
  }, [load]);

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1.5} sx={{ mb: 2 }}>
        <TextField id="ap-status" size="small" select label={t("status")} value={status} sx={{ minWidth: 200 }}
          onChange={(e) => setStatus(e.target.value as typeof status)}>
          <MenuItem value="">{t("status_all")}</MenuItem>
          {(["new", "accepted", "rejected"] as const).map((s) => <MenuItem key={s} value={s}>{t(`ap_${s}` as MessageKey)}</MenuItem>)}
        </TextField>
      </Stack>
      {!items.length && <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>{t("appeals_empty")}</Typography>}
      <Stack spacing={1.5} id="appeals-list">
        {items.map((a) => (
          <Box key={a.id} data-appeal={a.number} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 1.5,
            display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr auto" }, gap: 1, alignItems: "center" }}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography fontWeight={600}>{a.number} · {a.org_name}</Typography>
                <Chip size="small" color={a.status === "accepted" ? "success" : a.status === "rejected" ? "default" : "warning"}
                  label={t(`ap_${a.status}` as MessageKey)} />
                {a.waste_type === "septic" && <Chip size="small" color="info" label={t("w_septic")} />}
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {[districtLabel(districts, a.district_id), a.address, a.caller_name, a.caller_phone].filter(Boolean).join(" · ")}
              </Typography>
              <Typography variant="caption" color="text.secondary">{formatDateTime(new Date(a.created_at + "Z"))}{a.note && ` — ${a.note}`}</Typography>
              {a.reject_reason && <Typography variant="body2" color="error">{a.reject_reason}</Typography>}
            </Box>
            <Stack direction="row" spacing={1} justifyContent="flex-end">
              {a.status === "new" && can("appeals.review") && <Button variant="contained" onClick={() => setOpen(a)}>{t("review_appeal")}</Button>}
            </Stack>
          </Box>
        ))}
      </Stack>
      {open && <ReviewDialog appeal={open} districts={districts} onClose={() => setOpen(null)}
        onDone={(msg) => { toast(msg); setOpen(null); load(); }} onError={(e) => toast(tErr(errorCode(e), errorMessage(e)), "error")} />}
    </Paper>
  );
}

function ReviewDialog({ appeal, districts, onClose, onDone, onError }: {
  appeal: Appeal; districts: RefData["districts"]; onClose: () => void; onDone: (msg: string) => void; onError: (e: unknown) => void }) {
  const { t } = useI18n();
  const [card, setCard] = useState({ name: appeal.org_name, district_id: appeal.district_id, stir: appeal.stir ?? "", director: "",
    address: appeal.address ?? "", activity_type: appeal.activity_type ?? "", phone: appeal.caller_phone ?? "" });
  const [withContract, setWithContract] = useState(true);
  const [ct, setCt] = useState<ContractCreate>({ number: "", type: "per_trip", signed_on: today(), price: null, valid_from: today(),
    valid_to: `${new Date().getFullYear()}-12-31` });
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const stirBad = card.stir !== "" && !/^\d{9}$/.test(card.stir);
  const opt = (v: string) => v.trim() || null;

  const accept = async () => {
    setBusy(true);
    try {
      await appealsApi.accept(appeal.id, {
        customer: { name: card.name.trim(), district_id: card.district_id, stir: opt(card.stir), director: opt(card.director),
          address: opt(card.address), activity_type: opt(card.activity_type), phone: opt(card.phone) },
        contract: withContract ? { ...ct, number: ct.number.trim() } : null,
      });
      onDone(t("appeal_accepted_ok"));
    } catch (e) { onError(e); } finally { setBusy(false); }
  };
  const reject = async () => {
    setBusy(true);
    try { await appealsApi.reject(appeal.id, reason.trim()); onDone(t("saved")); } catch (e) { onError(e); } finally { setBusy(false); }
  };
  const f = (k: keyof typeof card, label: string, extra?: object) => (
    <TextField id={`rv-${k}`} size="small" label={label} value={card[k]} onChange={(e) => setCard({ ...card, [k]: e.target.value })} {...extra} />
  );

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{appeal.number} · {appeal.org_name}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Box sx={{ p: 1.5, bgcolor: "action.hover", borderRadius: 1 }}>
            <Typography variant="subtitle2">{t("appeal_order")}</Typography>
            <Typography variant="body2">
              {t(`wt_${appeal.waste_type}` as MessageKey)}{appeal.volume_estimate && `, ${appeal.volume_estimate} m³`}
              {appeal.preferred_time && `, ${appeal.preferred_time}`}{appeal.note && ` — ${appeal.note}`}
            </Typography>
            <Typography variant="body2" color="text.secondary">{[appeal.caller_name, appeal.caller_phone].filter(Boolean).join(" · ")}</Typography>
          </Box>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            {f("name", t("customer_name"), { sx: { gridColumn: { sm: "1 / -1" } } })}
            <TextField id="rv-district" size="small" select label={t("district")} value={card.district_id}
              onChange={(e) => setCard({ ...card, district_id: Number(e.target.value) })}>
              {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </TextField>
            {f("stir", t("stir"), { error: stirBad, slotProps: { htmlInput: { inputMode: "numeric", maxLength: 9 } } })}
            {f("director", t("director"))}
            {f("activity_type", t("activity_type"))}
            {f("phone", t("phone"))}
            {f("address", t("address"))}
          </Box>
          <FormControlLabel control={<Checkbox checked={withContract} onChange={(e) => setWithContract(e.target.checked)} />} label={t("with_contract")} />
          {withContract && <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" } }}>
            <TextField id="rv-ct-number" size="small" label={t("contract_no")} value={ct.number} onChange={(e) => setCt({ ...ct, number: e.target.value })} />
            <TextField id="rv-ct-type" size="small" select label={t("contract_type")} value={ct.type} onChange={(e) => setCt({ ...ct, type: e.target.value as ContractType })}>
              {CONTRACT_TYPES.map((x) => <MenuItem key={x} value={x}>{t(`ct_${x}` as MessageKey)}</MenuItem>)}
            </TextField>
            <TextField size="small" type="number" label={t("price")} value={ct.price ?? ""} onChange={(e) => setCt({ ...ct, price: e.target.value === "" ? null : Number(e.target.value) })} />
            <TextField size="small" type="date" label={t("valid_from")} value={ct.valid_from} InputLabelProps={{ shrink: true }} onChange={(e) => setCt({ ...ct, valid_from: e.target.value })} />
            <TextField size="small" type="date" label={t("valid_to")} value={ct.valid_to} InputLabelProps={{ shrink: true }} onChange={(e) => setCt({ ...ct, valid_to: e.target.value })} />
          </Box>}
          {rejecting && <TextField id="rv-reason" size="small" label={t("reject_reason")} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2, gap: 1, flexWrap: "wrap" }}>
        <Button onClick={onClose} disabled={busy}>{t("cancel")}</Button>
        {!rejecting ? <Button color="error" onClick={() => setRejecting(true)}>{t("reject_appeal")}</Button>
          : <Button color="error" variant="outlined" disabled={busy || reason.trim().length < 2} onClick={reject}>{t("reject_appeal")}</Button>}
        <Button id="rv-accept" variant="contained" disabled={busy || rejecting || card.name.trim().length < 2 || stirBad || (withContract && !ct.number.trim())}
          onClick={accept}>{t("accept_appeal")}</Button>
      </DialogActions>
    </Dialog>
  );
}
