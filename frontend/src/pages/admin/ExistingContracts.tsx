import { useRef, useState } from "react";
import { Alert, Button, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import UploadIcon from "@mui/icons-material/UploadFile";
import DownloadIcon from "@mui/icons-material/Download";
import { contractsApi } from "@/api/endpoints";
import { STAGE } from "@/components/Stage";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { ExistingImportResult } from "@/types";
import { saveBlob } from "./ContractWizard";


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
