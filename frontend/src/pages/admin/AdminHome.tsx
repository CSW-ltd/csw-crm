import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Paper, Stack, Tab, Tabs, Typography } from "@mui/material";
import { useLocation, useNavigate } from "react-router-dom";
import { useSituation } from "@/components/Situation";
import { useCan } from "@/hooks/useCan";
import { adminApi } from "@/api/endpoints";
import { useI18n } from "@/i18n/I18nContext";
import { useAppSelector } from "@/store";
import type { District, Region } from "@/types";
import { OrdersTab } from "./OrdersTab";
import { AdminCompaniesTab } from "./AdminCompaniesTab";
import { CompaniesTab } from "./CompaniesTab";
import { PaymentsTab } from "./PaymentsTab";
import { ContractWizard } from "./ContractWizard";
import { ContractsTab } from "./ContractsTab";
import NoteAddIcon from "@mui/icons-material/NoteAdd";
import { StatsTab } from "./StatsTab";
import { DistrictsTab } from "./DistrictsTab";
import { SettingsTab } from "./SettingsTab";
import { SituationTab } from "./SituationTab";
import { InvoicesTab, OrderFormsTab } from "./InvoicesTab";
import { UsersTab } from "./UsersTab";
import { VehiclesTab } from "./VehiclesTab";

const TABS = ["stats", "situation", "appeals", "companies", "contracts", "orderforms", "invoices", "payments", "customers", "users", "districts", "vehicles", "settings"] as const;
type TabId = (typeof TABS)[number];

export interface RefData { regions: Region[]; districts: District[]; reload: () => Promise<void>; canWrite: boolean }

// Yorliq → uni ko'rsatadigan ruxsat ("admin" — faqat admin)
const TAB_PERM: Record<TabId, string[] | "admin"> = {
  situation: "admin", stats: ["stats.view"], appeals: ["appeals.view", "orders.view", "requests.view"], customers: ["customers.view"], companies: ["accounting.view"], contracts: ["customers.contract", "accounting.payments"], orderforms: ["accounting.payments"], invoices: ["accounting.payments"], payments: ["accounting.payments"], users: ["staff.view"], districts: "admin",
  vehicles: ["vehicles.view"], settings: ["settings.view", "settings.radius_edit"],
};

/** Boshqaruv paneli: yorliqlar ruxsatlarga qarab (admin — hammasi). Server har amalni o'zi ham tekshiradi. */
export function AdminHome() {
  const { t } = useI18n();
  const role = useAppSelector((s) => s.auth.user?.role);
  const can = useCan();
  const canWrite = role === "admin";
  // Legal va buxgalter uchun «Korxonalar» — faqat statistika (debitor/kreditor); admin/manager — korxonalar bazasi
  const statsOnly = role === "legal" || role === "accountant";
  const tabs = TABS.filter((x) => (x === "companies" ? statsOnly : x === "customers" ? !statsOnly : true))
    .filter((x) => TAB_PERM[x] === "admin" ? role === "admin" : (TAB_PERM[x] as string[]).some(can));
  const [newContract, setNewContract] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  const situation = useSituation();
  // "#companies" (legal/buxgalter) ↔ "#customers" (admin/manager) — ikkalasi ham «Korxonalar»
  const hash = loc.hash === "#companies" && !statsOnly ? "#customers" : loc.hash === "#customers" && statsOnly ? "#companies" : loc.hash;
  const tab: TabId | undefined = tabs.find((x) => hash === `#${x}`) ?? tabs[0];
  const [regions, setRegions] = useState<Region[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);

  const reload = useCallback(async () => {
    const [r, d] = await Promise.all([adminApi.regions(), adminApi.districts()]);
    setRegions(r);
    setDistricts(d);
  }, []);
  useEffect(() => { reload().catch(() => undefined); }, [reload]);

  const ref: RefData = { regions, districts, reload, canWrite };
  // Yorliq URL'dagi #hash'da: qo'ng'iroqcha "/admin#situation" ga o'tkazadi
  const pick = (v: TabId) => nav({ hash: `#${v}` }, { replace: true });

  return (
    <Stack spacing={2}>
      <Typography variant="h5">{t(role === "admin" ? "admin_title" : tabs.length === 1 && tabs[0] === "customers" ? "customers_title" : "work_panel")}</Typography>
      {!tabs.length && <Alert severity="info">{t("no_panels")}</Alert>}
      <Paper variant="outlined">
        <Stack direction="row" alignItems="center">
        <Tabs value={tab ?? false} onChange={(_, v: TabId) => pick(v)} variant="scrollable" allowScrollButtonsMobile sx={{ flex: 1, minWidth: 0 }}>
          {tabs.map((x) => <Tab key={x} value={x} label={x === "situation" && situation?.unread
            ? <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>{t("tab_situation")}<CountPill n={situation.unread} /></Box>
            : t(`tab_${x}`)} />)}
        </Tabs>
        {role === "legal" && can("customers.create") && <Button id="new-contract" variant="contained" disableElevation startIcon={<NoteAddIcon />}
          onClick={() => setNewContract(true)} sx={{ mx: 1.5, flexShrink: 0, bgcolor: "#00A651", "&:hover": { bgcolor: "#008C44" } }}>
          {t("new_contract")}</Button>}
        </Stack>
      </Paper>
      {newContract && <ContractWizard districts={districts} onClose={() => setNewContract(false)} />}
      {tab === "situation" && <SituationTab {...ref} />}
      {tab === "stats" && <StatsTab {...ref} />}
      {tab === "appeals" && <OrdersTab {...ref} />}
      {tab === "customers" && <AdminCompaniesTab {...ref} />}
      {tab === "companies" && <CompaniesTab {...ref} />}
      {tab === "contracts" && <ContractsTab {...ref} />}
      {tab === "orderforms" && <OrderFormsTab {...ref} />}
      {tab === "invoices" && <InvoicesTab {...ref} />}
      {tab === "payments" && <PaymentsTab {...ref} />}
      {tab === "users" && <UsersTab {...ref} />}
      {tab === "districts" && <DistrictsTab {...ref} />}
      {tab === "vehicles" && <VehiclesTab {...ref} />}
      {tab === "settings" && <SettingsTab {...ref} />}
    </Stack>
  );
}

/** Yorliq ichidagi son: absolute badge emas — yorliq chegarasidan chiqmaydi va kesilmaydi. */
export function CountPill({ n }: { n: number }) {
  return <Box component="span" data-testid="count-pill" sx={{ minWidth: 20, height: 20, px: 0.75, borderRadius: 10, bgcolor: "error.main", color: "error.contrastText",
    fontSize: 12, fontWeight: 600, lineHeight: "20px", textAlign: "center", fontVariantNumeric: "tabular-nums" }}>{n > 99 ? "99+" : n}</Box>;
}

export function districtLabel(districts: District[], id: number | null | undefined): string {
  return districts.find((d) => d.id === id)?.name ?? "—";
}
