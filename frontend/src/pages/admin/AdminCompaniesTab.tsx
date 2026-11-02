import { useEffect, useState } from "react";
import { Box, Button, ButtonBase, MenuItem, Paper, Stack, Tab, Tabs, TextField, Typography } from "@mui/material";
import NoteAddIcon from "@mui/icons-material/NoteAdd";
import UploadIcon from "@mui/icons-material/UploadFile";
import { accountingApi, type NewPeriod } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { STAGE } from "@/components/Stage";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import type { RefData } from "./AdminHome";
import { CompaniesTab } from "./CompaniesTab";
import { ContractWizard } from "./ContractWizard";
import { CustomersTab } from "./CustomersTab";
import { ImportDialog } from "./ImportDialog";
import { usePersisted } from "@/hooks/usePersisted";

const PERIODS: NewPeriod[] = ["d7", "d15", "m1", "m6", "y1"];
type NC = Awaited<ReturnType<typeof accountingApi.newContracts>>;

/**
 * Admin/manager «Korxonalar»: «Statistika» (yangi shartnomalar 7/15/30/182/365 kun, debitor/kreditor jadvali —
 * tuman filtri hammasiga) va «Korxonalar bazasi». «Yangi shartnoma» va «Fayldan import» — ichki tablar qatorining o'ng chetida.
 */
export function AdminCompaniesTab(ref: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const [sub, setSub] = usePersisted<"stats" | "base">("cmp.sub", "stats");
  const [district, setDistrict] = usePersisted<number | "">("cmp.district", "");
  const [nc, setNc] = useState<NC | null>(null);
  const [period, setPeriod] = useState<NewPeriod>("m1");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [baseKey, setBaseKey] = useState(0);
  const canStats = can("accounting.view");

  useEffect(() => {
    if (!canStats) return;
    accountingApi.newContracts(district || undefined).then(setNc).catch((e) => toast(tErr(errorCode(e), errorMessage(e)), "error"));
  }, [district, canStats, tErr]);
  const tabSub = canStats ? sub : "base";

  return (
    <Stack spacing={2}>
      <Paper variant="outlined">
        <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ sm: "center" }}>
          <Tabs value={tabSub} onChange={(_, v) => setSub(v)} sx={{ flex: 1 }}>
            {canStats && <Tab value="stats" id="cmp-sub-stats" label={t("cmp_sub_stats")} />}
            <Tab value="base" id="cmp-sub-base" label={t("cmp_sub_base")} />
          </Tabs>
          <Stack direction="row" spacing={1} sx={{ px: 1.5, py: { xs: 1, sm: 0 } }}>
            {can("customers.import") && <Button id="cmp-import" size="large" variant="outlined" startIcon={<UploadIcon />}
              onClick={() => setImporting(true)} sx={{ borderWidth: 2, "&:hover": { borderWidth: 2 } }}>{t("import_excel")}</Button>}
            {can("customers.contract") && <Button id="cmp-new-contract" size="large" variant="contained" disableElevation startIcon={<NoteAddIcon />}
              onClick={() => setCreating(true)} sx={{ bgcolor: STAGE.green.bg, "&:hover": { bgcolor: STAGE.green.border } }}>{t("new_contract")}</Button>}
          </Stack>
        </Stack>
      </Paper>

      {tabSub === "stats" && <>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} justifyContent="space-between">
          <Typography variant="subtitle1" fontWeight={600}>{t("nc_title_stats")}</Typography>
          <TextField id="cmp-district" select size="small" label={t("district")} value={district} sx={{ minWidth: 220 }}
            onChange={(e) => setDistrict(e.target.value === "" ? "" : Number(e.target.value))}>
            <MenuItem value="">{t("all_districts")}</MenuItem>
            {ref.districts.filter((d) => d.is_active).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
          </TextField>
        </Stack>
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(5, 1fr)" } }} id="nc-panels">
          {PERIODS.map((p) => {
            const item = nc?.periods.find((x) => x.key === p);
            const on = period === p;
            return (
              <ButtonBase key={p} data-period={p} onClick={() => setPeriod(p)} focusRipple
                sx={{ display: "block", textAlign: "left", p: 2, borderRadius: 2, bgcolor: on ? STAGE.green.bg : "background.paper",
                  color: on ? "#fff" : "text.primary", border: 2, borderColor: on ? STAGE.green.border : "divider" }}>
                <Typography sx={{ fontSize: 32, fontWeight: 700, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" }} data-count>{item?.count ?? "—"}</Typography>
                <Typography variant="body2">{t(`nc_${p}` as MessageKey)}</Typography>
                {item && <Typography variant="caption" sx={{ opacity: 0.8 }}>{item.since} — {nc?.today}</Typography>}
              </ButtonBase>
            );
          })}
        </Box>
        <CompaniesTab {...ref} districtId={district || undefined} showDistrict backTo="/admin#customers" />
      </>}

      {tabSub === "base" && <CustomersTab key={baseKey} {...ref} hideActions />}
      {creating && <ContractWizard districts={ref.districts} onClose={() => setCreating(false)} onDone={() => setBaseKey((k) => k + 1)} />}
      {importing && <ImportDialog onClose={() => setImporting(false)} onImported={() => setBaseKey((k) => k + 1)} />}
    </Stack>
  );
}
