import { useState } from "react";
import { Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { adminApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { confirmDialog, toast } from "@/lib/alerts";
import type { District } from "@/types";
import type { RefData } from "./AdminHome";
import { TariffsTab } from "./TariffsTab";

type Form = { id?: number; name: string; region_id: number | "" };

export function DistrictsTab(ref: RefData) {
  // Admin: tumanlar ro'yxati va ularning ta'riflari (1 m³) shu bo'limda
  return (
    <Stack spacing={2}>
      <DistrictsList {...ref} />
      <TariffsTitle />
      <TariffsTab {...ref} />
    </Stack>
  );
}

function TariffsTitle() {
  const { t } = useI18n();
  return <Typography variant="h6" sx={{ pt: 1 }} id="tariffs-title">{t("tab_tariffs")}</Typography>;
}

function DistrictsList({ regions, districts, reload, canWrite }: RefData) {
  const { t, tErr } = useI18n();
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); toast(t("saved")); await reload(); return true; }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); return false; }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!form || form.region_id === "") return;
    const ok = await run(() => form.id ? adminApi.updateDistrict(form.id, { name: form.name }) : adminApi.createDistrict(form.name, form.region_id as number));
    if (ok) setForm(null);
  };
  const toggle = async (d: District) => {
    if (d.is_active && !(await confirmDialog(t("confirm_deactivate"), t("deactivate"), t("cancel"), d.name))) return;
    await run(() => adminApi.updateDistrict(d.id, { is_active: !d.is_active }));
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      {canWrite && <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
        <Button variant="contained" onClick={() => setForm({ name: "", region_id: regions[0]?.id ?? "" })}>{t("new_district")}</Button>
      </Stack>}
      {regions.map((r) => (
        <Stack key={r.id} sx={{ mb: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 0.5 }}>{r.name}</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead><TableRow><TableCell>{t("district")}</TableCell><TableCell>{t("status")}</TableCell>{canWrite && <TableCell />}</TableRow></TableHead>
              <TableBody>
                {districts.filter((d) => d.region_id === r.id).map((d) => (
                  <TableRow key={d.id} sx={{ opacity: d.is_active ? 1 : 0.55 }}>
                    <TableCell>{d.name}</TableCell>
                    <TableCell><Chip size="small" color={d.is_active ? "success" : "default"} label={t(d.is_active ? "active" : "inactive")} /></TableCell>
                    {canWrite && <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                      <Button size="small" onClick={() => setForm({ id: d.id, name: d.name, region_id: d.region_id })}>{t("edit")}</Button>
                      <Button size="small" color={d.is_active ? "error" : "success"} disabled={busy} onClick={() => toggle(d)}>{t(d.is_active ? "deactivate" : "activate")}</Button>
                    </TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      ))}

      <Dialog open={!!form} onClose={() => setForm(null)} fullWidth maxWidth="xs">
        <DialogTitle>{form?.id ? t("edit") : t("new_district")}</DialogTitle>
        {form && <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField id="d-region" select label={t("region")} value={form.region_id} disabled={!!form.id}
              onChange={(e) => setForm({ ...form, region_id: Number(e.target.value) })}>
              {regions.map((r) => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
            </TextField>
            <TextField id="d-name" label={t("district")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Stack>
        </DialogContent>}
        <DialogActions>
          <Button onClick={() => setForm(null)}>{t("cancel")}</Button>
          <Button variant="contained" onClick={save} disabled={busy || !form || form.name.trim().length < 2 || form.region_id === ""}>{t("save")}</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
