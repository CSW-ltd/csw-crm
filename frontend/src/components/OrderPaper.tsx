import { useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import PrintIcon from "@mui/icons-material/Print";
import { ordersApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import type { OrderPaper as Paper } from "@/types";

const MASK = "•••••••";

function Ln({ label, value, w = "100%" }: { label?: string; value?: string | null; w?: string }) {
  return (
    <Stack direction="row" alignItems="flex-end" spacing={0.75} sx={{ width: w, minWidth: 0 }}>
      {label && <Typography sx={{ fontSize: 12, whiteSpace: "nowrap" }}>{label}</Typography>}
      <Box sx={{ flex: 1, borderBottom: "1px solid #222", minHeight: 18, fontSize: 12.5, fontWeight: 700, px: 0.5, overflow: "hidden",
        whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{value ?? ""}</Box>
    </Stack>
  );
}

function Half({ p, copy, autofill }: { p: Paper; copy: string; autofill?: { volume?: string; kind?: "solid" | "liquid" | null } }) {
  const { t } = useI18n();
  const box = (on: boolean) => <Box component="span" sx={{ display: "inline-block", width: 11, height: 11, border: "1px solid #222",
    mr: 0.75, verticalAlign: "-1px", textAlign: "center", fontSize: 10, lineHeight: "10px" }}>{on ? "✓" : ""}</Box>;
  return (
    <Stack spacing={1.1} sx={{ flex: 1, minWidth: 0, color: "#1a1a1a" }}>
      <Box sx={{ textAlign: "center" }}>
        <Typography sx={{ fontWeight: 700, fontSize: 14 }}>Ko'rsatilgan xizmat bo'yicha</Typography>
        <Typography sx={{ fontWeight: 700, fontSize: 14 }}>BUYURTMA CHEKI</Typography>
        <Typography sx={{ fontSize: 10 }}>{copy}</Typography>
      </Box>
      <Typography sx={{ color: "#c8102e", fontWeight: 700, fontSize: 24, textAlign: "right", fontFamily: "ui-monospace, monospace" }}>
        № {p.form.number}
      </Typography>
      <Ln label="20__ yil «__»" w="60%" />
      <Stack direction="row" spacing={2}><Ln label="soat" value="" w="50%" /><Ln label="gacha" w="50%" /></Stack>
      <Box>
        <Typography sx={{ fontWeight: 700, fontSize: 13 }}>«{p.provider || "BIO TEXNO KLASTER"}» MChJ</Typography>
        <Typography sx={{ fontSize: 10 }}>(Xizmat ko'rsatuvchi tashkilot nomi)</Typography>
      </Box>
      <Ln label="Tashkilot nomi:" value={p.customer.name} />
      <Stack direction="row" spacing={2}>
        <Ln label="Maxsus raqami:" value={p.customer.code} w="50%" />
        <Ln label="Murojaat:" value={p.request_number} w="50%" />
      </Stack>
      <Ln label="Manzili:" value={p.customer.address} />
      <Ln label="Olib chiqilgan chiqindi miqdori:" value={autofill?.volume ? `${autofill.volume} metr kub` : ""} />
      <Typography sx={{ fontWeight: 700, fontSize: 12.5 }}>Olib chiqilgan chiqindi turini belgilang:</Typography>
      <Stack direction="row" spacing={3} sx={{ fontSize: 12.5 }}>
        <span>{box(autofill?.kind === "solid")}Qattiq maishiy chiqindi</span>
        <span>{box(autofill?.kind === "liquid")}Suyuq maishiy chiqindi</span>
      </Stack>
      <Typography sx={{ fontWeight: 700, fontSize: 12.5 }}>Xizmat ko'rsatuvchi maxsus texnika haqida ma'lumot</Typography>
      <Stack direction="row" spacing={2}>
        <Ln label="Davlat raqami:" value={p.vehicle?.plate} w="55%" />
        <Ln label="Rusumi:" value={p.vehicle?.model} w="45%" />
      </Stack>
      <Ln label="Haydovchi F.I.Sh.:" value={p.driver_name} />
      <Stack direction="row" spacing={1}><Ln label="Buyurtmachi:" w="45%" /><Ln w="25%" /><Ln w="30%" /></Stack>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Box>
          <Typography sx={{ fontSize: 10, color: "#666" }}>{t("of_code_label")}</Typography>
          <Box data-masked-code sx={{ border: "1px solid #222", px: 1.25, py: 0.25, fontFamily: "ui-monospace, monospace", fontWeight: 700,
            letterSpacing: 3, display: "inline-block" }}>{MASK}</Box>
        </Box>
        <Typography sx={{ fontWeight: 700 }}>M.O'.</Typography>
      </Stack>
    </Stack>
  );
}

/** Varaqaning qog'oz ko'rinishi: ikki qism, qirqish chizig'i. Maxfiy kod ekranda doim yashirin. */
export function PaperSheet({ p, autofill }: { p: Paper; autofill?: { volume?: string; kind?: "solid" | "liquid" | null } }) {
  return (
    <Box id="order-paper" sx={{ bgcolor: "#fffdf7", border: "1px solid #d6d0c2", borderRadius: 1, boxShadow: "0 2px 10px rgba(0,0,0,.08)",
      p: { xs: 1.5, sm: 2.5 }, display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 2.5, color: "#1a1a1a" }}>
      <Half p={p} copy="(buyurtmachi tashkilotga beriladigan 1-nusxa)" autofill={autofill} />
      <Box sx={{ borderLeft: { md: "2px dashed #999" }, borderTop: { xs: "2px dashed #999", md: "none" }, position: "relative", minWidth: 2 }}>
        <Typography sx={{ position: "absolute", top: { xs: -9, md: "40%" }, left: { xs: "50%", md: -7 }, writingMode: { md: "vertical-rl" },
          transform: { xs: "translateX(-50%)", md: "none" }, fontSize: 10, color: "#777", whiteSpace: "nowrap", bgcolor: "#fffdf7",
          px: { xs: 0.5, md: 0 }, py: { md: 0.5 } }}>✂ Qirqish chizig'i</Typography>
      </Box>
      <Half p={p} copy="(xizmat ko'rsatuvchi tashkilotga beriladigan 2-nusxa)" autofill={autofill} />
    </Box>
  );
}

async function printBlob(blob: Blob) {
  const url = URL.createObjectURL(blob);
  const frame = document.createElement("iframe");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  frame.src = url;
  document.body.appendChild(frame);
  frame.onload = () => {
    try { frame.contentWindow?.focus(); frame.contentWindow?.print(); } catch { window.open(url, "_blank"); }
    window.setTimeout(() => { frame.remove(); URL.revokeObjectURL(url); }, 60_000);
  };
}

/** GPS: biriktirilgandan keyin bo'sh varaqa (faqat raqami bilan) va "Chop etish". Qayta chop etish — manager ruxsati bilan. */
export function OrderPaperDialog({ formId, onClose, onChanged }: { formId: number; onClose: () => void; onChanged?: () => void }) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [p, setP] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");
  const load = () => ordersApi.paper(formId).then(setP).catch((e) => { fail(e); onClose(); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [formId]);

  const [asked, setAsked] = useState(false);
  const doPrint = async () => {
    setBusy(true);
    try { await printBlob(await ordersApi.print(formId)); await load(); onChanged?.(); setAsked(true); } catch (e) { fail(e); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    setBusy(true);
    try { await ordersApi.confirmPrint(formId); toast(t("of_confirmed_ok")); onChanged?.(); onClose(); } catch (e) { fail(e); }
    finally { setBusy(false); }
  };
  const allow = async () => {
    try { await ordersApi.allowReprint(formId); toast(t("saved")); await load(); onChanged?.(); } catch (e) { fail(e); }
  };
  const f = p?.form;
  // Printerdan chiqqani tasdiqlanmaguncha — o'sha raqam bilan erkin qayta chop etiladi
  const canPrint = !!f && can("orders.print") && !f.closed_at && (!f.printed || f.reprint_allowed || !!p?.awaiting_print);
  // Qayta biriktirilgan: qog'ozda eski mashina — yangisi bilan qayta chop etilmaguncha tasdiq yo'q
  const waiting = !!p?.awaiting_print && !!f?.printed && !p?.needs_reprint;

  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>{t("of_title")} № {f?.number ?? ""}</DialogTitle>
      <DialogContent dividers sx={{ bgcolor: "#f1efe9" }}>
        {!p ? <Stack alignItems="center" sx={{ py: 6 }}><CircularProgress /></Stack> : <>
          {p?.needs_reprint && <Alert severity="error" sx={{ mb: 2 }} id="of-needs-reprint">{t("of_needs_reprint")}</Alert>}
          {waiting && <Alert severity="warning" sx={{ mb: 2 }} id="of-await-confirm"
            action={p?.manual_confirm && can("orders.print") ? <Stack direction="row" spacing={1}>
              <Button id="of-confirm" color="success" variant="contained" disableElevation size="small" disabled={busy} onClick={confirm}>{t("of_confirm_yes")}</Button>
              <Button id="of-reprint" color="inherit" size="small" disabled={busy} onClick={doPrint}>{t("of_confirm_no")}</Button>
            </Stack> : undefined}>
            <b>{t(p?.manual_confirm ? "of_confirm_q" : "of_wait_agent")}</b>{asked ? "" : ` ${t("of_confirm_hint")}`}</Alert>}
          {f?.printed && !f.reprint_allowed && !waiting && <Alert severity="info" sx={{ mb: 2 }} id="of-printed-info">
            {t("of_already_printed", { at: f.printed_at ? formatDateTime(new Date(f.printed_at + "Z")) : "", n: f.print_count })}</Alert>}
          {f?.reprint_allowed && <Alert severity="warning" sx={{ mb: 2 }}>{t("of_reprint_allowed")}</Alert>}
          <PaperSheet p={p} />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>{t("of_code_hint")}</Typography>
        </>}
      </DialogContent>
      <DialogActions>
        {f?.printed && !f.reprint_allowed && !f.closed_at && can("orders.unlock") &&
          <Button id="of-allow-reprint" onClick={allow} sx={{ mr: "auto" }}>{t("of_allow_reprint")}</Button>}
        <Button onClick={onClose}>{t("close")}</Button>
        {can("orders.print") && <Button id="of-print" variant="contained" disableElevation startIcon={<PrintIcon />} disabled={!canPrint || busy}
          onClick={doPrint}>{t(waiting ? "of_print_again" : "of_print")}</Button>}
      </DialogActions>
    </Dialog>
  );
}
