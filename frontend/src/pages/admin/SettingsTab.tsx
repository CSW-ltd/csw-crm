import { useEffect, useState } from "react";
import { Box, Button, FormControlLabel, MenuItem, Paper, Select, Slider, Stack, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField,
  Typography } from "@mui/material";
import { adminApi, providersApi } from "@/api/endpoints";
import { onlyDigits } from "@/components/DigitsField";
import { errorCode, errorMessage } from "@/api/client";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { useAppSelector } from "@/store";
import type { DistrictRadius, ProviderReq } from "@/types";
import type { MessageKey } from "@/i18n/messages";
import type { RefData } from "./AdminHome";
import { TariffsTab } from "./TariffsTab";

const MARKS = [100, 150, 200, 250, 300].map((v) => ({ value: v, label: `${v} m` }));
const OPTIONS = Array.from({ length: 21 }, (_, i) => 100 + i * 10);

/** Umumiy GPS radiusi (faqat admin) va tumanlar bo'yicha radius (settings.radius_edit — o'z tumanlari). */
export function SettingsTab(ref: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const role = useAppSelector((s) => s.auth.user?.role);
  const isAdmin = role === "admin";
  const canDistrict = can("settings.radius_edit");
  const [saved, setSaved] = useState<number | null>(null);
  const [radius, setRadius] = useState(300);
  const [rows, setRows] = useState<DistrictRadius[]>([]);
  const [busy, setBusy] = useState(false);

  const apply = (s: { gps_radius_m: number; districts: DistrictRadius[] }) => { setSaved(s.gps_radius_m); setRadius(s.gps_radius_m); setRows(s.districts); };
  useEffect(() => { adminApi.settings().then(apply).catch(() => undefined); }, []);

  const run = async (fn: () => Promise<{ gps_radius_m: number; districts: DistrictRadius[] }>) => {
    setBusy(true);
    try { apply(await fn()); toast(t("saved")); }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
    finally { setBusy(false); }
  };

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack spacing={2} sx={{ maxWidth: 520 }}>
          <Typography variant="subtitle1" fontWeight={600}>{t("radius_default_title")}: <span style={{ fontVariantNumeric: "tabular-nums" }}>{radius} m</span></Typography>
          <Typography variant="body2" color="text.secondary">{t("gps_radius_hint")}</Typography>
          <Box sx={{ px: 1 }}>
            <Slider value={radius} min={100} max={300} step={10} marks={MARKS} disabled={!isAdmin || saved === null}
              onChange={(_e, v) => setRadius(v as number)} aria-label={t("gps_radius")} />
          </Box>
          {isAdmin && <Box><Button variant="contained" onClick={() => run(() => adminApi.saveSettings(radius))}
            disabled={busy || saved === null || radius === saved}>{t("save")}</Button></Box>}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600}>{t("radius_by_district")}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("radius_by_district_hint")}</Typography>
        <Table size="small" id="district-radius">
          <TableHead><TableRow><TableCell>{t("district")}</TableCell><TableCell>{t("gps_radius")}</TableCell>
            <TableCell>{t("print_mode")}</TableCell></TableRow></TableHead>
          <TableBody>
            {rows.map((d) => (
              <TableRow key={d.id} data-district={d.name}>
                <TableCell>{d.name}</TableCell>
                <TableCell>
                  {canDistrict
                    ? <Select size="small" value={d.gps_radius_m ?? ""} displayEmpty disabled={busy} sx={{ minWidth: 170 }}
                      onChange={(e) => run(() => adminApi.saveDistrictRadius(d.id, e.target.value === "" ? null : Number(e.target.value)))}>
                      <MenuItem value="">{t("radius_common", { m: saved ?? 300 })}</MenuItem>
                      {OPTIONS.map((m) => <MenuItem key={m} value={m}>{m} m</MenuItem>)}
                    </Select>
                    : <span>{d.gps_radius_m ? `${d.gps_radius_m} m` : t("radius_common", { m: d.effective_m })}</span>}
                </TableCell>
                <TableCell>
                  {isAdmin
                    ? <FormControlLabel control={<Switch size="small" checked={d.print_manual_confirm !== false} disabled={busy} data-print-mode={d.id}
                        onChange={(e) => run(() => adminApi.setPrintMode(d.id, e.target.checked))} />}
                        label={t(d.print_manual_confirm !== false ? "print_mode_manual" : "print_mode_agent")} />
                    : <span>{t(d.print_manual_confirm !== false ? "print_mode_manual" : "print_mode_agent")}</span>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
      <Requisites isAdmin={isAdmin} />
      {/* Manager: o'z tumanlari ta'rifi shu yerda (admin uchun — «Tumanlar» bo'limida) */}
      {role === "manager" && <><Typography variant="h6" sx={{ pt: 1 }} id="tariffs-title">{t("tab_tariffs")}</Typography><TariffsTab {...ref} /></>}
    </Stack>
  );
}

const DIG: Partial<Record<keyof ProviderReq, number>> = { inn: 9, mfo: 5, account: 20, oked: 5 };
const REQ_FIELDS: { k: keyof ProviderReq; w: number; pattern?: RegExp }[] = [
  { k: "full_name", w: 2 }, { k: "inn", w: 1, pattern: /^\d{9}$/ }, { k: "address", w: 2 }, { k: "phone", w: 1 }, { k: "bank", w: 2 },
  { k: "mfo", w: 1, pattern: /^\d{5}$/ }, { k: "account", w: 2, pattern: /^\d{20}$/ }, { k: "oked", w: 1, pattern: /^\d{4,5}$/ },
  { k: "director", w: 2 }, { k: "chief_accountant", w: 1 },
];

/** Xizmat ko'rsatuvchi (viloyat bo'yicha) rekvizitlari — schyot-faktura PDF'iga chiqadi. Tahrirlash — faqat admin. */
function Requisites({ isAdmin }: { isAdmin: boolean }) {
  const { t, tErr } = useI18n();
  const [list, setList] = useState<ProviderReq[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => { providersApi.list().then(setList).catch(() => undefined); }, []);
  const set = (id: number, k: keyof ProviderReq, v: string) => setList((l) => l.map((p) => (p.id === id ? { ...p, [k]: v } : p)));
  const save = async (p: ProviderReq) => {
    const bad = REQ_FIELDS.find((f) => f.pattern && p[f.k] && !f.pattern.test(String(p[f.k])));
    if (bad) { toast(t("req_invalid", { f: t(`req_${bad.k}` as MessageKey) }), "error"); return; }
    setBusy(p.id);
    try {
      const body = Object.fromEntries(REQ_FIELDS.map((f) => [f.k, (p[f.k] as string | null) || null]));
      const r = await providersApi.save(p.id, body);
      setList((l) => l.map((x) => (x.id === r.id ? r : x)));
      toast(t("saved"));
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); } finally { setBusy(null); }
  };
  if (!list.length) return null;
  return (
    <Paper variant="outlined" sx={{ p: 3 }} id="requisites">
      <Typography variant="subtitle1" fontWeight={600}>{t("req_title")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("req_hint")}</Typography>
      <Stack spacing={3}>
        {list.map((p) => (
          <Box key={p.id} data-provider={p.code}>
            <Typography fontWeight={600} sx={{ mb: 1 }}>{p.name} ({p.code})</Typography>
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
              {REQ_FIELDS.map((f) => (
                <TextField key={f.k} size="small" label={t(`req_${f.k}` as MessageKey)} value={(p[f.k] as string | null) ?? ""} disabled={!isAdmin}
                  name={f.k} onChange={(e) => set(p.id, f.k, f.pattern ? onlyDigits(e.target.value, DIG[f.k] ?? 20) : e.target.value)}
                  inputProps={f.pattern ? { inputMode: "numeric", maxLength: DIG[f.k] } : undefined} sx={{ gridColumn: { md: `span ${f.w}` } }}
                  error={!!(f.pattern && p[f.k] && !f.pattern.test(String(p[f.k])))} />
              ))}
            </Box>
            {isAdmin && <Button sx={{ mt: 1.5 }} variant="contained" disableElevation disabled={busy === p.id} onClick={() => save(p)}
              data-save-provider={p.code}>{t("save")}</Button>}
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
