import { Alert, Badge, Box, Button, Stack, Tab, Tabs, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { SoundToggle, useAlertSound, useNewItemsSignal, useNow } from "@/components/Stage";
import { GreenCard, YellowCard } from "@/components/StageCards";
import { useI18n } from "@/i18n/I18nContext";
import { useAppDispatch, useAppSelector } from "@/store";
import { refreshDriver } from "@/store/driverSlice";
import { usePersisted } from "@/hooks/usePersisted";

/** Haydovchi (smenasiz): «Biriktirilgan murojaatlar» — sariq, timer bilan; «Bajarilganlar» — yashil. Yangi biriktirilsa — ovozli alert. */
export function DriverHome() {
  const { t } = useI18n();
  const nav = useNavigate();
  const dispatch = useAppDispatch();
  const now = useNow();
  const sound = useAlertSound();
  const { today, tasks, done, loaded } = useAppSelector((s) => s.driver);
  const [tab, setTab] = usePersisted<"assigned" | "done">("driver.tab", "assigned");
  useNewItemsSignal(tasks.map((x) => x.id), loaded, () => sound.play("yellow"));

  if (!loaded) return <Typography>{t("loading")}</Typography>;
  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} flexWrap="wrap" useFlexGap>
        <Box>
          <Typography variant="h6">{t("drv_title")}</Typography>
          <Typography variant="body2" color="text.secondary">
            {today?.vehicle ? t("drv_today_vehicle", { plate: today.vehicle.plate, service: t(today.service === "individual" ? "svc_individual" : "svc_legal") })
              : t("drv_no_schedule")}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <SoundToggle on={sound.on} toggle={sound.toggle} />
          <Button size="small" onClick={() => dispatch(refreshDriver())}>{t("refresh")}</Button>
        </Stack>
      </Stack>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
        <Tab value="assigned" id="drv-tab-assigned" label={<Badge color="warning" badgeContent={tasks.length} sx={{ pr: 1.5 }}>{t("drv_tab_assigned")}</Badge>} />
        <Tab value="done" id="drv-tab-done" label={t("drv_tab_done")} />
      </Tabs>
      {tab === "assigned" && <Stack spacing={1.5} id="drv-assigned">
        {tasks.length === 0 && <Alert severity="info">{t("no_tasks")}</Alert>}
        {tasks.map((task) => (
          <YellowCard key={task.id} r={task} now={now}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button size="large" variant="contained" disableElevation color="inherit" onClick={() => nav(`/driver/requests/${task.id}`)}
                sx={{ bgcolor: "#5b4300", color: "#fff", "&:hover": { bgcolor: "#3d2d00" } }}>{t("drv_open_act")}</Button>
            </Stack>
          </YellowCard>
        ))}
      </Stack>}
      {tab === "done" && <Stack spacing={1} id="drv-done">
        {done.length === 0 && <Typography color="text.secondary">{t("ord_no_green")}</Typography>}
        {done.map((r) => <GreenCard key={r.id} r={r} />)}
      </Stack>}
    </Stack>
  );
}
