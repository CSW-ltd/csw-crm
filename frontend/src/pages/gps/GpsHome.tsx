import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Badge, Box, Button, Chip, CircularProgress, Divider, IconButton, ListItemText, Menu, MenuItem, Paper, Select, Stack, Tab, Tabs,
  TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowDownIcon from "@mui/icons-material/ArrowDownward";
import ArrowUpIcon from "@mui/icons-material/ArrowUpward";
import DeleteIcon from "@mui/icons-material/DeleteOutline";
import ExpandIcon from "@mui/icons-material/ExpandMore";
import PrintIcon from "@mui/icons-material/Print";
import { gpsApi, requestsApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { OrderPaperDialog } from "@/components/OrderPaper";
import { SoundToggle, useAlertSound, useNewItemsSignal, useNow } from "@/components/Stage";
import { RedCard, YellowCard } from "@/components/StageCards";
import { useOnline } from "@/hooks/useOnline";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { getSocket } from "@/lib/socket";
import { useAppSelector } from "@/store";
import type { DriverTask, RequestItem, ScheduleDay, ScheduleRow, VehicleOption } from "@/types";
import { usePersisted } from "@/hooks/usePersisted";

type GpsFilter = "new" | "today" | "repeat" | "overdue" | "all";
const FILTERS: GpsFilter[] = ["new", "today", "repeat", "overdue", "all"];
const isToday = (iso: string) => new Date(iso + "Z").toDateString() === new Date().toDateString();
const MATCH: Record<GpsFilter, (r: DriverTask) => boolean> = {
  new: (r) => r.seen === false, today: (r) => isToday(r.created_at), repeat: (r) => !!r.is_repeat, overdue: (r) => !!r.overdue,
  all: () => true,
};
const km = (m: number | null) => (m == null ? "—" : m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`);
const localDay = (offset = 0) => { const d = new Date(Date.now() + 5 * 3600_000 + offset * 86_400_000); return d.toISOString().slice(0, 10); };

/**
 * GPS xodimi: qizil kartalar (mashina biriktirilmagan, 72 soat timer, ovozli alert) → mashina tanlash (bugungi ish jadvalidan,
 * yuridik bo'lim mashinalari yuqorida, masofa bo'yicha) → buyurtma varaqasi chop etiladi va karta sariq bo'ladi.
 */
export function GpsHome() {
  const { t, tErr } = useI18n();
  const now = useNow();
  const sound = useAlertSound();
  const [tab, setTab] = usePersisted<"red" | "yellow" | "schedule">("gps.tab", "red");
  const [red, setRed] = useState<DriverTask[]>([]);
  const [yellow, setYellow] = useState<RequestItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = usePersisted<GpsFilter>("gps.filter", "new");
  const [seenNow, setSeenNow] = useState<Set<number>>(new Set());
  const [paper, setPaper] = useState<number | null>(null);
  const user = useAppSelector((s) => s.auth.user);

  const load = useCallback(async () => {
    const [r, y] = await Promise.all([gpsApi.newRequests(),
      requestsApi.list({ stage: "yellow", district_id: user?.district_id ?? undefined, limit: 200 })]);
    setRed(r); setYellow(y.items); setLoaded(true);
  }, [user?.district_id]);

  useEffect(() => {
    load().catch(() => undefined);
    const s = getSocket();
    const onUpdate = () => { load().catch(() => undefined); };
    s.on("request:updated", onUpdate);
    const poll = window.setInterval(onUpdate, 30_000);
    return () => { s.off("request:updated", onUpdate); window.clearInterval(poll); };
  }, [load]);
  useNewItemsSignal(red.map((r) => r.id), loaded, () => sound.play("red"));

  const isNew = (r: DriverTask) => r.seen === false && !seenNow.has(r.id);
  const counts = Object.fromEntries(FILTERS.map((f) => [f, f === "new" ? red.filter(isNew).length : red.filter(MATCH[f]).length]));
  const shown = red.filter((r) => MATCH[filter](r) || (filter === "new" && seenNow.has(r.id)));
  const markSeen = (ids: number[]) => {
    const fresh = ids.filter((id) => red.find((r) => r.id === id)?.seen === false && !seenNow.has(id));
    if (!fresh.length) return;
    setSeenNow((s) => new Set([...s, ...fresh]));
    requestsApi.markSeen(fresh).catch(() => undefined);
  };
  const pickFilter = (f: GpsFilter) => {
    setFilter(f);
    if (seenNow.size) { setRed((rs) => rs.map((r) => (seenNow.has(r.id) ? { ...r, seen: true } : r))); setSeenNow(new Set()); }
  };
  const onAssigned = async (res: DriverTask) => {
    toast(t("gps_assigned_ok", { plate: res.vehicle?.plate ?? "", n: res.order_form?.number ?? "" }));
    await load();
    if (res.order_form) setPaper(res.order_form.id);
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2} flexWrap="wrap" useFlexGap>
        <Typography variant="h5">{t("gps_title")}</Typography>
        <SoundToggle on={sound.on} toggle={sound.toggle} />
      </Stack>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tab value="red" id="gps-tab-red" label={<Badge color="error" badgeContent={red.length} sx={{ pr: 1.5 }}>{t("gps_tab_red")}</Badge>} />
        <Tab value="yellow" id="gps-tab-yellow" label={<Badge color="warning" badgeContent={yellow.length} sx={{ pr: 1.5 }}>{t("gps_tab_yellow")}</Badge>} />
        <Tab value="schedule" id="gps-tab-schedule" label={t("gps_tab_schedule")} />
      </Tabs>

      {tab === "red" && <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap" id="gps-filters" role="tablist">
          {FILTERS.map((f) => <Chip key={f} data-filter={f} role="tab" aria-selected={filter === f} clickable onClick={() => pickFilter(f)}
            color={filter === f ? "primary" : "default"} variant={filter === f ? "filled" : "outlined"}
            label={<Box component="span" sx={{ fontVariantNumeric: "tabular-nums" }}>{t(`gf_${f}`)} · {counts[f]}</Box>} />)}
          <Button size="small" sx={{ ml: "auto" }} disabled={!counts.new} onClick={() => markSeen(red.filter(isNew).map((r) => r.id))}>{t("gf_mark_all")}</Button>
        </Stack>
        {loaded && red.length === 0 && <Alert severity="success">{t("no_new_requests")}</Alert>}
        {red.length > 0 && shown.length === 0 && <Typography color="text.secondary">{t("gf_empty")}</Typography>}
        <Stack spacing={1.5} id="gps-list">
          {shown.map((r) => (
            <Box key={r.id} onClick={() => markSeen([r.id])}>
              <RedCard r={r} now={now} isNew={isNew(r)}>
                {r.status === "printing" && r.order_form
                  ? <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} data-awaiting-print>
                    <Chip icon={<PrintIcon sx={{ color: "#fff !important" }} />} label={t("of_awaiting_print", { n: r.order_form.number, plate: r.vehicle?.plate ?? "" })}
                      sx={{ bgcolor: "rgba(0,0,0,.3)", color: "#fff", fontWeight: 600 }} />
                    <Button variant="contained" disableElevation startIcon={<PrintIcon />} onClick={(e) => { e.stopPropagation(); setPaper(r.order_form!.id); }}
                      sx={{ bgcolor: "#fff", color: "#8b0f0f", fontWeight: 700, "&:hover": { bgcolor: "#ffe3e3" } }}>{t("of_open_print")}</Button>
                  </Stack>
                  : <AssignBar r={r} onDone={onAssigned} onError={(e) => toast(tErr(errorCode(e), errorMessage(e)), "error")} />}
              </RedCard>
            </Box>
          ))}
        </Stack>
      </Stack>}

      {tab === "yellow" && <Stack spacing={1.5} id="gps-yellow">
        {loaded && yellow.length === 0 && <Typography color="text.secondary">{t("gps_no_yellow")}</Typography>}
        {yellow.map((r) => (
          <YellowCard key={r.id} r={r} now={now}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {r.order_form && <Button size="small" variant={r.order_form.printed ? "outlined" : "contained"} color="inherit" disableElevation
                startIcon={<PrintIcon />} onClick={() => setPaper(r.order_form!.id)}>{t(r.order_form.printed ? "of_open" : "of_print")}</Button>}
            </Stack>
          </YellowCard>
        ))}
      </Stack>}

      {tab === "schedule" && <ScheduleSection />}
      {paper && <OrderPaperDialog formId={paper} onClose={() => setPaper(null)} onChanged={() => load().catch(() => undefined)} />}
    </Stack>
  );
}

/** Qizil kartadagi mashina tanlash: bugungi jadval, yuridik bo'lim mashinalari yuqorida, masofa bo'yicha o'sish/kamayish. */
function AssignBar({ r, onDone, onError }: { r: DriverTask; onDone: (res: DriverTask) => void; onError: (e: unknown) => void }) {
  const { t } = useI18n();
  const online = useOnline();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [opts, setOpts] = useState<VehicleOption[] | null>(null);
  const [hasLoc, setHasLoc] = useState(true);
  const [asc, setAsc] = useState(true);
  const [pick, setPick] = useState<VehicleOption | null>(null);
  const [busy, setBusy] = useState(false);
  const blocked = r.customer.missing_fields.length > 0;

  const open = async (el: HTMLElement) => {
    setAnchor(el);
    try { const x = await gpsApi.vehicleOptions(r.id); setOpts(x.items); setHasLoc(x.customer_has_location); } catch (e) { onError(e); setAnchor(null); }
  };
  const sorted = useMemo(() => {
    if (!opts) return [];
    const rank = (o: VehicleOption) => (o.service === "legal" ? 0 : o.service === "individual" ? 1 : 2);
    return [...opts].sort((a, b) => rank(a) - rank(b)
      || (a.distance_m == null ? 1 : 0) - (b.distance_m == null ? 1 : 0)
      || (asc ? 1 : -1) * ((a.distance_m ?? 0) - (b.distance_m ?? 0)) || a.plate.localeCompare(b.plate));
  }, [opts, asc]);
  const assign = async () => {
    if (!pick) return;
    setBusy(true);
    try { onDone(await gpsApi.assign(r.id, pick.vehicle_id)); } catch (e) { onError(e); } finally { setBusy(false); }
  };

  if (blocked) return <Alert severity="warning" variant="filled" sx={{ bgcolor: "rgba(0,0,0,.35)" }}>{t("cannot_assign_contract")}</Alert>;
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} onClick={(e) => e.stopPropagation()}>
      <Button data-vehicle-picker variant="contained" disableElevation endIcon={<ExpandIcon />} onClick={(e) => open(e.currentTarget)}
        sx={{ bgcolor: "transparent", color: "#fff", border: "2px solid rgba(255,255,255,.85)", "&:hover": { bgcolor: "rgba(255,255,255,.12)" },
          justifyContent: "space-between", minWidth: 260 }}>
        {pick ? `${pick.plate} · ${pick.driver_name ?? ""} · ${km(pick.distance_m)}` : t("gps_pick_vehicle")}
      </Button>
      <Button data-assign variant="contained" disableElevation disabled={!pick || busy || !online} onClick={assign}
        sx={{ bgcolor: "#fff", color: "#8b0f0f", fontWeight: 700, border: "2px solid #fff", "&:hover": { bgcolor: "#ffe3e3" },
          "&.Mui-disabled": { bgcolor: "rgba(0,0,0,.22)", color: "rgba(255,255,255,.75)", borderColor: "rgba(255,255,255,.35)" } }}>
        {busy ? <CircularProgress size={18} color="inherit" /> : t("gps_assign_vehicle")}
      </Button>
      <Box sx={{ ml: { sm: "auto" }, "& .MuiButton-root": { color: "#fff", borderColor: "rgba(255,255,255,.6)" } }}>
      </Box>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} PaperProps={{ sx: { width: 380, maxHeight: 440 } }}>
        <Stack direction="row" alignItems="center" sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2" sx={{ flex: 1 }}>{t("gps_vehicles_today")}</Typography>
          <Button size="small" id="vehicle-sort" onClick={() => setAsc((v) => !v)} endIcon={asc ? <ArrowUpIcon /> : <ArrowDownIcon />}>
            {t("gps_distance")}</Button>
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ px: 2, display: "block", mt: -0.5, mb: 0.5 }}>{t("gps_sort_distance")}</Typography>
        {!hasLoc && <Typography variant="caption" color="text.secondary" sx={{ px: 2, display: "block" }}>{t("gps_no_customer_location")}</Typography>}
        <Divider />
        {!opts && <Stack alignItems="center" sx={{ py: 3 }}><CircularProgress size={22} /></Stack>}
        {opts && !opts.length && <Typography sx={{ p: 2 }} color="text.secondary">{t("no_free_vehicles")}</Typography>}
        {sorted.map((o) => (
          <MenuItem key={o.vehicle_id} data-vehicle={o.plate} disabled={!o.available} selected={pick?.vehicle_id === o.vehicle_id}
            onClick={() => { setPick(o); setAnchor(null); }} sx={{ alignItems: "flex-start", gap: 1 }}>
            <ListItemText primary={<Stack direction="row" spacing={1} alignItems="center">
              <span style={{ fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>{o.plate}</span>
              <Chip size="small" label={t(o.service ? `svc_${o.service}` : "svc_none")} color={o.service === "legal" ? "primary" : "default"}
                variant={o.service === "legal" ? "filled" : "outlined"} sx={{ height: 20 }} /></Stack>}
              secondary={o.available ? `${o.driver_name} · ${o.model ?? ""}` : t("gps_not_in_schedule")} />
            <Typography sx={{ fontVariantNumeric: "tabular-nums", fontWeight: 600, whiteSpace: "nowrap" }} data-distance>{km(o.distance_m)}</Typography>
          </MenuItem>
        ))}
      </Menu>
    </Stack>
  );
}

/** Kunlik ish jadvali: mashina → haydovchi → xizmat turi (yuridik / jismoniy, mahallalar). GPS-monitoring ham shuni o'qiydi. */
function ScheduleSection() {
  const { t, tErr } = useI18n();
  const [day, setDay] = useState(localDay());
  const [data, setData] = useState<ScheduleDay | null>(null);
  const [rows, setRows] = useState<ScheduleRow[]>([]);
  const [busy, setBusy] = useState(false);
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");
  const load = useCallback(async () => {
    try { const d = await gpsApi.schedule(day); setData(d); setRows(d.rows); } catch (e) { fail(e); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day]);
  useEffect(() => { load(); }, [load]);

  const set = (i: number, patch: Partial<ScheduleRow>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const used = new Set(rows.map((r) => r.vehicle_id));
  const free = data?.vehicles.filter((v) => !used.has(v.id)) ?? [];
  const add = () => free[0] && setRows((rs) => [...rs, { vehicle_id: free[0].id, driver_id: null, service: "legal", mahallas: null }]);
  const save = async () => {
    setBusy(true);
    try { setRows(await gpsApi.saveSchedule(rows, day)); toast(t("saved")); } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const copy = async () => {
    setBusy(true);
    try { setRows(await gpsApi.copySchedule(localDay(-1))); toast(t("sch_copied")); } catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }} id="schedule">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mb: 2 }}>
        <TextField size="small" type="date" label={t("sch_day")} value={day} onChange={(e) => setDay(e.target.value)} InputLabelProps={{ shrink: true }} />
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>{t("sch_hint")}</Typography>
        {day === localDay() && <Button id="sch-copy" onClick={copy} disabled={busy}>{t("sch_copy_yesterday")}</Button>}
      </Stack>
      {!data ? <CircularProgress size={24} /> : <Stack spacing={1}>
        {rows.length === 0 && <Alert severity="info">{t("sch_empty")}</Alert>}
        {rows.map((r, i) => (
          <Box key={i} data-sch-row={i} sx={{ display: "grid", gap: 1, alignItems: "center",
            gridTemplateColumns: { xs: "1fr 1fr", md: "170px 1fr 150px 1fr 40px" } }}>
            <Select size="small" value={r.vehicle_id} onChange={(e) => set(i, { vehicle_id: Number(e.target.value) })}>
              {data.vehicles.filter((v) => v.id === r.vehicle_id || !used.has(v.id)).map((v) =>
                <MenuItem key={v.id} value={v.id}>{v.plate}</MenuItem>)}
            </Select>
            <Select size="small" displayEmpty value={r.driver_id ?? ""} onChange={(e) => set(i, { driver_id: e.target.value === "" ? null : Number(e.target.value) })}>
              <MenuItem value="">{t("sch_no_driver")}</MenuItem>
              {data.drivers.map((d) => <MenuItem key={d.id} value={d.id}
                disabled={rows.some((x, j) => j !== i && x.driver_id === d.id)}>{d.full_name}</MenuItem>)}
            </Select>
            <Select size="small" value={r.service} onChange={(e) => set(i, { service: e.target.value as ScheduleRow["service"] })}>
              <MenuItem value="legal">{t("svc_legal")}</MenuItem>
              <MenuItem value="individual">{t("svc_individual")}</MenuItem>
            </Select>
            <TextField size="small" placeholder={t("sch_mahallas")} value={r.mahallas ?? ""} disabled={r.service === "legal"}
              onChange={(e) => set(i, { mahallas: e.target.value })} inputProps={{ maxLength: 500 }} />
            <IconButton aria-label={t("delete")} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}><DeleteIcon /></IconButton>
          </Box>
        ))}
        <Stack direction="row" spacing={1} sx={{ pt: 1 }}>
          <Button startIcon={<AddIcon />} onClick={add} disabled={!free.length}>{t("sch_add")}</Button>
          <Box sx={{ flex: 1 }} />
          <Button id="sch-save" variant="contained" disableElevation onClick={save} disabled={busy}>{t("save")}</Button>
        </Stack>
      </Stack>}
    </Paper>
  );
}
