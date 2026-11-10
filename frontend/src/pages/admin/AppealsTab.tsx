import { useCallback, useEffect, useState } from "react";
import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { appealsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import { getSocket } from "@/lib/socket";
import type { Appeal } from "@/types";
import { districtLabel, type RefData } from "./AdminHome";
import { ContractWizard } from "./ContractWizard";
import { usePersisted } from "@/hooks/usePersisted";

/** Yangi korxona murojaatlari — «Yangi shartnomaga yo'naltirilgan»: yurist shu yerdan shartnoma tuzadi (korxona = kontragent,
 * murojaatda yaratilmaydi); shartnoma raqam olganda murojaat yopiladi. Yoki izoh bilan rad etadi. */
export function AppealsTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [status, setStatus] = usePersisted<"new" | "accepted" | "rejected" | "">("appeals.status", "new");
  const [items, setItems] = useState<Appeal[]>([]);
  const [rejecting, setRejecting] = useState<Appeal | null>(null);
  const [contractFor, setContractFor] = useState<Appeal | null>(null);

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
              {a.status === "new" && can("appeals.review") && <>
                <Button color="error" onClick={() => setRejecting(a)}>{t("reject_appeal")}</Button>
                {can("customers.contract") && <Button variant="contained" disableElevation data-to-contract onClick={() => setContractFor(a)}>
                  {t("appeal_to_contract")}</Button>}
              </>}
            </Stack>
          </Box>
        ))}
      </Stack>
      {rejecting && <RejectDialog appeal={rejecting} onClose={() => setRejecting(null)}
        onDone={() => { toast(t("saved")); setRejecting(null); load(); }} onError={(e) => toast(tErr(errorCode(e), errorMessage(e)), "error")} />}
      {contractFor && <ContractWizard districts={districts} appeal={contractFor} onClose={() => { setContractFor(null); load().catch(() => undefined); }}
        onDone={() => load().catch(() => undefined)} />}
    </Paper>
  );
}

function RejectDialog({ appeal, onClose, onDone, onError }: {
  appeal: Appeal; onClose: () => void; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const reject = async () => {
    setBusy(true);
    try { await appealsApi.reject(appeal.id, reason.trim()); onDone(); } catch (e) { onError(e); } finally { setBusy(false); }
  };
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{appeal.number} · {appeal.org_name}</DialogTitle>
      <DialogContent dividers>
        <TextField id="rv-reason" size="small" fullWidth label={t("reject_reason")} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} disabled={busy}>{t("cancel")}</Button>
        <Button color="error" variant="contained" disableElevation disabled={busy || reason.trim().length < 2} onClick={reject}>{t("reject_appeal")}</Button>
      </DialogActions>
    </Dialog>
  );
}
