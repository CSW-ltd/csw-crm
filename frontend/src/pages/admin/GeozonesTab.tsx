import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Chip, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  Typography } from "@mui/material";
import UploadIcon from "@mui/icons-material/UploadFile";
import { dispatchApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import type { GpsImportReport, GpsImportSummary } from "@/types";
import type { RefData } from "./AdminHome";

const MAX_MB = 10;

/** Admin: GPS eksport (csw-gps-agent gps_eksport.py) zip'ini import qilish — geozonalar, mahallalar, tayoqcha/chegara,
 *  mashina ↔ GPS obyekti. Avval «Tekshirish» (bazaga yozmaydi), har bo'lim CRM tumaniga bog'lanadi, keyin «Import». */
export function GeozonesTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [sum, setSum] = useState<GpsImportSummary | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rep, setRep] = useState<GpsImportReport | null>(null);
  const [mapping, setMapping] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error"), [tErr]);
  const loadSum = useCallback(() => dispatchApi.summary().then(setSum).catch(fail), [fail]);
  useEffect(() => { loadSum(); }, [loadSum]);

  const check = async (f: File, m: Record<string, number>) => {
    setBusy(true);
    try {
      const r = await dispatchApi.preview(f, m);
      // Oldingi importdagi bog'lanish taklif qilinadi (admin o'zgartira oladi)
      const auto = { ...m };
      r.sections.forEach((s) => { if (auto[s.tuman] === undefined && s.suggested_district_id) auto[s.tuman] = s.suggested_district_id; });
      if (Object.keys(auto).length !== Object.keys(m).length) { setMapping(auto); setRep(await dispatchApi.preview(f, auto)); }
      else setRep(r);
    } catch (e) { fail(e); setRep(null); } finally { setBusy(false); }
  };
  const pick = (f: File | null) => {
    setRep(null); setMapping({});
    if (f && f.size > MAX_MB * 1024 * 1024) { toast(t("gz_too_large", { n: MAX_MB }), "error"); setFile(null); return; }
    setFile(f);
  };
  const setDistrict = (tuman: string, v: number | "") => {
    const m = { ...mapping };
    if (v === "") delete m[tuman]; else m[tuman] = v;
    setMapping(m);
    if (file) check(file, m);
  };
  const run = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const r = await dispatchApi.apply(file, mapping);
      const s = r.stats!;
      toast(t("gz_done", { z: r.zones.total, n: r.zones.new, c: r.zones.changed, d: r.zones.deactivated, m: s.mahallas_created,
        u: s.mahallas_updated, x: s.mahallas_deactivated, v: s.vehicles_linked }), "success");
      setRep(null); setFile(null); setMapping({});
      await loadSum();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const mapped = Object.keys(mapping).length;
  const dName = (id: number | null) => districts.find((d) => d.id === id)?.name ?? "—";

  return (
    <Stack spacing={2} id="geozones">
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("gz_summary")}</Typography>
        <TableContainer><Table size="small" id="gz-summary">
          <TableHead><TableRow><TableCell>{t("district")}</TableCell><TableCell align="right">{t("gz_mahallas")}</TableCell>
            <TableCell align="right">{t("gz_sticks")}</TableCell><TableCell align="right">{t("gz_boundaries")}</TableCell>
            <TableCell align="right">{t("gz_vehicles")}</TableCell></TableRow></TableHead>
          <TableBody>
            {sum?.districts.map((r) => <TableRow key={r.district_id} data-district={r.district_id}>
              <TableCell>{r.district}</TableCell><TableCell align="right">{r.mahallas}</TableCell><TableCell align="right">{r.sticks}</TableCell>
              <TableCell align="right">{r.boundaries}{r.boundaries < r.mahallas && <Chip size="small" color="warning" variant="outlined" sx={{ ml: 0.5 }}
                label={t("gz_no_boundary_n", { n: r.mahallas - r.boundaries })} />}</TableCell>
              <TableCell align="right">{r.vehicles_linked}</TableCell></TableRow>)}
            {sum && !sum.districts.length && <TableRow><TableCell colSpan={5}><Typography color="text.secondary">{t("gz_empty")}</Typography></TableCell></TableRow>}
          </TableBody>
        </Table></TableContainer>
        {sum?.sources.map((s) => <Typography key={s.id} variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
          {s.server} · {s.account} — {t("gz_source_zones", { n: s.zones })}{s.updated_at ? ` · ${s.updated_at.slice(0, 16).replace("T", " ")}` : ""}</Typography>)}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={600}>{t("gz_import")}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{t("gz_import_hint", { n: MAX_MB })}</Typography>
        <input ref={input} id="gz-file" type="file" hidden accept=".zip" onChange={(e) => { pick(e.target.files?.[0] ?? null); e.target.value = ""; }} />
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => input.current?.click()} disabled={busy}>{file ? file.name : t("pay_pick_file")}</Button>
          {file && !rep && <Button id="gz-check" variant="outlined" disabled={busy} onClick={() => check(file, mapping)}>{t("pay_check")}</Button>}
        </Stack>

        {rep && <Box sx={{ mt: 2 }} id="gz-preview">
          <Alert severity="info">{t("gz_zones", { s: rep.server, a: rep.account, z: rep.zones.total, l: rep.zones.line, p: rep.zones.polygon,
            c: rep.zones.circle, n: rep.zones.new, ch: rep.zones.changed, d: rep.zones.deactivated })}</Alert>
          <TableContainer sx={{ mt: 1 }}><Table size="small" id="gz-sections">
            <TableHead><TableRow><TableCell>{t("gz_section")}</TableCell><TableCell sx={{ minWidth: 200 }}>{t("gz_crm_district")}</TableCell>
              <TableCell align="right">{t("gz_mahallas")}</TableCell><TableCell align="right">{t("gz_sticks")}</TableCell>
              <TableCell align="right">{t("gz_boundaries")}</TableCell><TableCell>{t("gz_vehicles")}</TableCell></TableRow></TableHead>
            <TableBody>{rep.sections.map((s) => <TableRow key={s.tuman} data-section={s.tuman} sx={{ verticalAlign: "top" }}>
              <TableCell><b>{s.tuman}</b>{s.missing_zones > 0 && <Typography variant="caption" color="error" display="block">
                {t("gz_missing_zones", { n: s.missing_zones })}</Typography>}</TableCell>
              <TableCell><TextField select size="small" fullWidth value={mapping[s.tuman] ?? ""} disabled={busy} data-map={s.tuman}
                onChange={(e) => setDistrict(s.tuman, e.target.value === "" ? "" : Number(e.target.value))}>
                <MenuItem value="">{t("gz_skip")}</MenuItem>
                {districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
              </TextField>
                {s.suggested_district_id && mapping[s.tuman] === s.suggested_district_id && <Typography variant="caption" color="text.secondary">
                  {t("gz_suggested")}</Typography>}</TableCell>
              <TableCell align="right">{s.mahallas}</TableCell><TableCell align="right">{s.sticks}</TableCell>
              <TableCell align="right">{s.boundaries}{s.no_boundary.length > 0 && <Typography variant="caption" color="text.secondary" display="block"
                title={s.no_boundary.join(", ")}>{t("gz_no_boundary_n", { n: s.no_boundary.length })}</Typography>}</TableCell>
              <TableCell>{s.district_id
                ? <><Typography variant="body2">{t("gz_vehicles_matched", { n: s.vehicles_matched, u: s.units })}</Typography>
                  {s.vehicles_missing.length > 0 && <Typography variant="caption" color="warning.main" display="block">
                    {t("gz_vehicles_missing", { list: s.vehicles_missing.join(", ") })}</Typography>}
                  {s.units_unmatched.length > 0 && <Typography variant="caption" color="text.secondary" display="block">
                    {t("gz_units_unmatched", { list: s.units_unmatched.slice(0, 15).join(", ") + (s.units_unmatched.length > 15 ? "…" : "") })}</Typography>}</>
                : <Typography variant="caption" color="text.secondary">{t("gz_units", { n: s.units })}</Typography>}</TableCell>
            </TableRow>)}</TableBody>
          </Table></TableContainer>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>{t("gz_check_hint")}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
            <Button onClick={() => { setRep(null); setFile(null); setMapping({}); }} disabled={busy}>{t("cancel")}</Button>
            <Button id="gz-apply" variant="contained" disableElevation disabled={!mapped || busy} onClick={run}>
              {t("gz_apply", { n: mapped })}</Button>
          </Stack>
          {mapped > 0 && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
            {rep.sections.filter((s) => mapping[s.tuman]).map((s) => `${s.tuman} → ${dName(mapping[s.tuman])}`).join(" · ")}</Typography>}
        </Box>}
      </Paper>
    </Stack>
  );
}
