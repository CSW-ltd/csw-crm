import { useRef, useState } from "react";
import { Alert, Box, Button, Chip, FormControlLabel, MenuItem, Paper, Radio, RadioGroup, Stack, Table, TableBody, TableCell, TableHead, TableRow,
  TextField, Typography } from "@mui/material";
import UploadIcon from "@mui/icons-material/UploadFile";
import DownloadIcon from "@mui/icons-material/Download";
import { contractsApi } from "@/api/endpoints";
import { STAGE } from "@/components/Stage";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { ContractType, ExistingImportResult } from "@/types";
import { saveBlob } from "./ContractWizard";

const TYPES: ContractType[] = ["by_volume", "per_trip", "monthly", "one_off"];
const PLATFORMS = ["didox", "hujjat", "soliq", "other"] as const;
const todayIso = () => new Date(Date.now() + 5 * 3600_000).toISOString().slice(0, 10);

/** Mavjud (allaqachon imzolangan) shartnomani bittalab kiritish: darhol «Tasdiqlangan». Kub turida hisob — ta'rif bo'yicha. */
export function ExistingContractForm({ customer, fail, onDone }: { customer: { id: number; name: string }; fail: (e: unknown) => void;
  onDone: () => void }) {
  const { t } = useI18n();
  const [f, setF] = useState({ number: "", platform: "didox", platform_id: "", type: "by_volume" as ContractType, price: "", annual_volume: "",
    signed_on: "", valid_from: "", valid_to: "", sign_method: "paper" as "electronic" | "paper" });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const ready = f.number.trim() && f.signed_on && f.valid_from && f.valid_to && (f.type === "by_volume" || Number(f.price) > 0)
    && (f.sign_method === "paper" || f.platform_id.trim());
  const submit = async () => {
    setBusy(true);
    try {
      const c = await contractsApi.createExisting({ customer_id: customer.id, number: f.number.trim(), type: f.type,
        platform: f.sign_method === "electronic" ? f.platform : null, platform_id: f.sign_method === "electronic" ? f.platform_id.trim() : null,
        price: f.type === "by_volume" ? null : Number(f.price), annual_volume: f.annual_volume ? Number(f.annual_volume) : null,
        signed_on: f.signed_on, valid_from: f.valid_from, valid_to: f.valid_to, sign_method: f.sign_method });
      if (file) await contractsApi.uploadScan(c.id, file);
      toast(t("ex_saved", { n: c.display_number }), "success");
      onDone();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <Stack spacing={2} id="ex-form">
      <Alert severity="info" variant="outlined">{t("ex_hint", { name: customer.name })}</Alert>
      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
        <TextField size="small" name="ex_number" label={t("contract_no")} value={f.number} onChange={(e) => set("number", e.target.value)} required />
        <TextField size="small" select name="ex_type" label={t("contract_type")} value={f.type} onChange={(e) => set("type", e.target.value)}>
          {TYPES.map((x) => <MenuItem key={x} value={x}>{t(`ct_${x}` as MessageKey)}</MenuItem>)}
        </TextField>
        {f.type === "by_volume"
          ? <TextField size="small" label={t("ctr_price_tariff")} value={t("ex_by_tariff")} InputProps={{ readOnly: true }} />
          : <TextField size="small" name="ex_price" type="number" label={`${t("ctr_price")} (${t("ctr_vat_incl")})`} value={f.price}
              onChange={(e) => set("price", e.target.value)} required />}
        <TextField size="small" name="ex_volume" type="number" label={t("ctr_annual_volume")} value={f.annual_volume}
          onChange={(e) => set("annual_volume", e.target.value)} />
        <TextField size="small" name="ex_signed" type="date" label={t("signed_on")} value={f.signed_on} InputLabelProps={{ shrink: true }}
          inputProps={{ max: todayIso() }} onChange={(e) => set("signed_on", e.target.value)} />
        <Box />
        <TextField size="small" name="ex_from" type="date" label={t("valid_from")} value={f.valid_from} InputLabelProps={{ shrink: true }}
          onChange={(e) => set("valid_from", e.target.value)} />
        <TextField size="small" name="ex_to" type="date" label={t("valid_to")} value={f.valid_to} InputLabelProps={{ shrink: true }}
          onChange={(e) => set("valid_to", e.target.value)} />
        <RadioGroup row value={f.sign_method} onChange={(e) => set("sign_method", e.target.value)}>
          <FormControlLabel value="paper" control={<Radio size="small" />} label={t("ctr_m_paper")} />
          <FormControlLabel value="electronic" control={<Radio size="small" />} label={t("ctr_m_electronic")} />
        </RadioGroup>
        {f.sign_method === "electronic" && <>
          <TextField size="small" select label={t("ctr_platform")} value={f.platform} onChange={(e) => set("platform", e.target.value)}>
            {PLATFORMS.map((p) => <MenuItem key={p} value={p}>{t(`ctr_pl_${p}` as MessageKey)}</MenuItem>)}
          </TextField>
          <TextField size="small" name="ex_pid" label={t("ctr_platform_id")} value={f.platform_id} onChange={(e) => set("platform_id", e.target.value)} required />
        </>}
      </Box>
      <Box>
        <input ref={ref} type="file" hidden accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button size="small" onClick={() => ref.current?.click()}>{t("ctr_attach_scan")}</Button>
        {file && <Chip size="small" label={file.name} onDelete={() => setFile(null)} sx={{ ml: 1 }} />}
      </Box>
      <Box><Button id="ex-save" variant="contained" disableElevation disabled={busy || !ready} onClick={submit}
        sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("ex_save")}</Button></Box>
    </Stack>
  );
}

/** Excel orqali ko'plab mavjud shartnomani kiritish: shablon → sinov (xatolar) → import. */
export function ExistingImport({ fail, onDone }: { fail: (e: unknown) => void; onDone: () => void }) {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<ExistingImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    try {
      const r = await contractsApi.importExisting(file, dry);
      setRes(r);
      if (!dry) { toast(t("ex_imported", { n: r.created }), "success"); onDone(); }
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <Stack spacing={2} id="ex-import">
      <Alert severity="info" variant="outlined">{t("ex_import_hint")}</Alert>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
        <Button variant="outlined" startIcon={<DownloadIcon />} id="ex-template"
          onClick={() => contractsApi.existingTemplate().then((b) => saveBlob(b, "mavjud_shartnomalar_shablon.xlsx")).catch(fail)}>{t("ex_template")}</Button>
        <input ref={ref} type="file" hidden accept=".xlsx,.xls,.csv" id="ex-file" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setRes(null); }} />
        <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => ref.current?.click()}>{file ? file.name : t("ex_choose_file")}</Button>
        <Button id="ex-dry" variant="contained" disableElevation disabled={!file || busy} onClick={() => run(true)}>{t("ex_dry")}</Button>
      </Stack>
      {res && <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography data-ex-summary>{t("ex_summary", { ok: res.ok, err: res.errors.length, total: res.total })}</Typography>
        {res.errors.length > 0 && <Table size="small" sx={{ mt: 1 }}>
          <TableHead><TableRow><TableCell>{t("ex_line")}</TableCell><TableCell>{t("ex_value")}</TableCell><TableCell>{t("ex_error")}</TableCell></TableRow></TableHead>
          <TableBody>{res.errors.slice(0, 200).map((e, i) => <TableRow key={i} data-ex-error={e.error}><TableCell>{e.line}</TableCell><TableCell>{e.value}</TableCell>
            <TableCell>{t(`exe_${e.error}` as MessageKey)}</TableCell></TableRow>)}</TableBody>
        </Table>}
        {res.dry_run && res.ok > 0 && <Button id="ex-run" sx={{ mt: 1.5, bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }} variant="contained"
          disableElevation disabled={busy} onClick={() => run(false)}>{t("ex_run", { n: res.ok })}</Button>}
      </Paper>}
    </Stack>
  );
}
