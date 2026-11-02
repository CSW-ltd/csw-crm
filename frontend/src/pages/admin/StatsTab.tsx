import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Box, Button, ButtonBase, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, ToggleButton, ToggleButtonGroup,
  Typography, useColorScheme } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { statsApi, type StatDetail, type StatMetric, type StatPeriod } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import type { StatMetrics, Stats } from "@/types";
import type { RefData } from "./AdminHome";
import { usePersisted } from "@/hooks/usePersisted";

const METRICS: StatMetric[] = ["received", "repeat", "pending", "overdue", "done", "not_done"];
const SHARE: Partial<Record<StatMetric, keyof StatMetrics>> = { done: "done_share", not_done: "not_done_share" };

// Ranglar (dataviz palitrasi): bitta seriya — brend rangi; tarkib — kategorial 1–3 (CVD-xavfsiz),
// "Bajarilgan" tarkibi — holat ranglari (yorliq va % bilan, rang yolg'iz ma'no tashimaydi).
const COLORS = {
  light: { series: "#1d6b4f", grid: "#e4e7e3", axis: "#52514e", surface: "#ffffff", cat: ["#2a78d6", "#eb6834", "#1baf7a"] },
  dark: { series: "#4fbf8c", grid: "#2c342f", axis: "#c3c2b7", surface: "#1a211d", cat: ["#3987e5", "#d95926", "#199e70"] },
};
const STATUS = { on_time: "#0ca30c", late: "#fab219", suspect: "#ec835a" } as Record<string, string>;

function useReducedMotion() {
  const [r, setR] = useState(() => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const on = () => setR(m.matches);
    m?.addEventListener?.("change", on);
    return () => m?.removeEventListener?.("change", on);
  }, []);
  return r;
}

/** Son 0 dan qiymatgacha "sanab" chiqadi (statistik animatsiya); kamaytirilgan harakat sozlamasida darhol. */
function CountUp({ value, reduced }: { value: number; reduced: boolean }) {
  const [v, setV] = useState(reduced ? value : 0);
  const from = useRef(0);
  useEffect(() => {
    if (reduced) { setV(value); return; }
    const start = performance.now(), a = from.current, dur = 800;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(a + (value - a) * e));
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduced]);
  return <>{v}</>;
}

function ChartCard({ id, title, subtitle, chart, table }: { id: string; title: string; subtitle?: string; chart: ReactNode; table: ReactNode }) {
  const { t } = useI18n();
  const [view, setView] = usePersisted<"chart" | "table">("stats.view", "chart");
  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 0 }} id={id}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{ mb: 1 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle1" fontWeight={600}>{title}</Typography>
          {subtitle && <Typography variant="caption" color="text.secondary">{subtitle}</Typography>}
        </Box>
        <ToggleButtonGroup size="small" exclusive value={view} onChange={(_e, v) => v && setView(v)}>
          <ToggleButton value="chart" sx={{ px: 1.25, py: 0.25 }}>{t("st_chart")}</ToggleButton>
          <ToggleButton value="table" sx={{ px: 1.25, py: 0.25 }}>{t("st_table")}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      {view === "chart" ? <Box sx={{ height: 260 }}>{chart}</Box> : <Box sx={{ maxHeight: 260, overflow: "auto" }}>{table}</Box>}
    </Paper>
  );
}

function SimpleTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <Table size="small" stickyHeader>
      <TableHead><TableRow>{head.map((h, i) => <TableCell key={h} align={i ? "right" : "left"}>{h}</TableCell>)}</TableRow></TableHead>
      <TableBody>{rows.map((r, i) => <TableRow key={i}>{r.map((c, j) =>
        <TableCell key={j} align={j ? "right" : "left"} sx={{ fontVariantNumeric: "tabular-nums" }}>{c}</TableCell>)}</TableRow>)}</TableBody>
    </Table>
  );
}

/**
 * Statistika: davr × ko'rsatkich. Kartochka bosilsa to'rtala diagramma faqat shu ko'rsatkich bo'yicha chiziladi:
 * Area (dinamika), Pie (tarkib), Histogramma (bajarilish vaqti), Bar (tumanlar). Har biri jadval ko'rinishiga o'tadi;
 * Excel/PDF — tanlangan davr va ko'rsatkich bo'yicha.
 */
export function StatsTab(_: RefData) {
  const { t, tErr } = useI18n();
  const { mode, systemMode } = useColorScheme();
  const c = COLORS[(mode === "system" ? systemMode : mode) === "dark" ? "dark" : "light"];
  const reduced = useReducedMotion();
  const [period, setPeriod] = usePersisted<StatPeriod>("stats.period", "today");
  const [metric, setMetric] = usePersisted<StatMetric>("stats.metric", "received");
  const [data, setData] = useState<Stats | null>(null);
  const [detail, setDetail] = useState<StatDetail | null>(null);
  const [exporting, setExporting] = useState<"" | "xlsx" | "pdf">("");
  const fail = (e: unknown) => toast(tErr(errorCode(e), errorMessage(e)), "error");

  useEffect(() => { statsApi.summary(period).then(setData).catch(fail); /* eslint-disable-next-line */ }, [period]);
  useEffect(() => { statsApi.detail(period, metric).then(setDetail).catch(fail); /* eslint-disable-next-line */ }, [period, metric]);

  const label = (m: StatMetric) => t(`st_${m}` as MessageKey);
  const anim = { isAnimationActive: !reduced, animationDuration: 900, animationEasing: "ease-out" as const };
  const axis = { stroke: c.axis, fontSize: 12, tickLine: false, axisLine: false };
  const tooltip = { contentStyle: { background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 13 },
    labelStyle: { color: c.axis }, cursor: { fill: c.grid, opacity: 0.4 } };
  const comp = useMemo(() => (detail?.composition ?? []).map((x, i) => ({
    name: t(`cmp_${x.key}` as MessageKey), value: x.value, key: x.key, fill: metric === "done" ? STATUS[x.key] : c.cat[i % 3] })), [detail, metric, c, t]);
  const compTotal = comp.reduce((s, x) => s + x.value, 0);
  const districts = useMemo(() => [...(detail?.districts ?? [])].sort((a, b) => b.value - a.value || a.name.localeCompare(b.name)), [detail]);
  // diagrammalar yangi ma'lumot kelganda qaytadan animatsiya bilan chiziladi (eski ma'lumot yangi kalit bilan chizilmasin)
  const key = detail ? `${detail.period}-${detail.metric}` : "";

  const doExport = async (format: "xlsx" | "pdf") => {
    setExporting(format);
    try { await statsApi.export(period, metric, format); } catch (e) { fail(e); } finally { setExporting(""); }
  };

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }} justifyContent="space-between">
        <ToggleButtonGroup size="small" exclusive value={period} onChange={(_e, v: StatPeriod | null) => v && setPeriod(v)} id="st-period">
          {(["today", "last5", "last10", "month"] as const).map((p) => <ToggleButton key={p} value={p} sx={{ px: 2 }}>{t(`p_${p}` as MessageKey)}</ToggleButton>)}
        </ToggleButtonGroup>
        <Stack direction="row" spacing={1} alignItems="center">
          {data && <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>{t("st_since", { d: formatDateTime(new Date(data.since + "Z")) })}</Typography>}
          <Button id="st-export-xlsx" size="small" variant="outlined" startIcon={<DownloadIcon />} disabled={!!exporting} onClick={() => doExport("xlsx")}>Excel</Button>
          <Button id="st-export-pdf" size="small" variant="outlined" startIcon={<DownloadIcon />} disabled={!!exporting} onClick={() => doExport("pdf")}>PDF</Button>
        </Stack>
      </Stack>



      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(3, 1fr)", lg: "repeat(6, 1fr)" } }}>
        {METRICS.map((m) => {
          const active = m === metric, share = SHARE[m];
          return (
            <ButtonBase key={m} data-metric={m} onClick={() => setMetric(m)} focusRipple aria-pressed={active}
              sx={{ display: "block", textAlign: "left", p: 2, borderRadius: 2, border: 1.5, bgcolor: "background.paper",
                borderColor: active ? "primary.main" : "divider", boxShadow: active ? "0 0 0 1px var(--mui-palette-primary-main) inset" : "none",
                "&:focus-visible": { outline: "2px solid", outlineColor: "primary.main", outlineOffset: 2 } }}>
              <Typography component="p" sx={{ fontSize: 30, fontWeight: 600, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" }}>
                {data ? <CountUp value={data.total[m]} reduced={reduced} /> : "—"}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{label(m)}</Typography>
              {share && data && <Typography variant="caption" color="text.secondary">{t("st_share", { p: data.total[share] })}</Typography>}
            </ButtonBase>
          );
        })}
      </Box>
      <Typography variant="caption" color="text.secondary">{t("st_click_hint")}</Typography>

      {data && <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>{t("st_all_table")}</Typography>
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small" id="st-table">
            <TableHead><TableRow>
              <TableCell>{t("district")}</TableCell>
              {METRICS.map((m) => <TableCell key={m} align="right" sx={{ fontWeight: m === metric ? 700 : 400 }}>{label(m)}</TableCell>)}
            </TableRow></TableHead>
            <TableBody>
              {[...data.districts, { ...data.total, district_id: 0, name: t("st_total") }].map((r) => (
                <TableRow key={r.district_id} sx={r.district_id === 0 ? { "& td": { fontWeight: 700 } } : undefined}>
                  <TableCell>{r.name}</TableCell>
                  {METRICS.map((m) => <TableCell key={m} align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                    {r[m]}{SHARE[m] && <Typography component="span" variant="caption" color="text.secondary"> {r[SHARE[m]!]}%</Typography>}
                  </TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </Paper>}

      {detail && <Box key={key} sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <ChartCard id="st-area" title={t("st_area_title", { metric: label(metric) })}
          subtitle={t(detail.granularity === "hour" ? "st_by_hour" : "st_by_day")}
          chart={<ResponsiveContainer>
            <AreaChart data={detail.series} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
              <defs><linearGradient id="st-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c.series} stopOpacity={0.35} /><stop offset="100%" stopColor={c.series} stopOpacity={0.02} />
              </linearGradient></defs>
              <CartesianGrid vertical={false} stroke={c.grid} />
              <XAxis dataKey="label" {...axis} minTickGap={12} />
              <YAxis allowDecimals={false} {...axis} width={40} />
              <Tooltip {...tooltip} cursor={{ stroke: c.axis, strokeDasharray: "3 3" }} formatter={(v: number) => [v, label(metric)]} />
              <Area type="monotone" dataKey="value" stroke={c.series} strokeWidth={2} fill="url(#st-fill)" dot={false}
                activeDot={{ r: 5, stroke: c.surface, strokeWidth: 2 }} {...anim} />
            </AreaChart>
          </ResponsiveContainer>}
          table={<SimpleTable head={[t(detail.granularity === "hour" ? "st_hour" : "date"), label(metric)]}
            rows={detail.series.map((p) => [p.label, p.value])} />} />

        <ChartCard id="st-pie" title={t("st_pie_title", { metric: label(metric) })} subtitle={t("st_total_n", { n: compTotal })}
          chart={compTotal === 0 ? <Stack sx={{ height: "100%" }} alignItems="center" justifyContent="center"><Typography color="text.secondary">{t("st_no_data")}</Typography></Stack>
            : <ResponsiveContainer>
              <PieChart>
                <Pie data={comp} dataKey="value" nameKey="name" innerRadius="45%" outerRadius="80%" paddingAngle={0} stroke={c.surface} strokeWidth={2}
                  label={({ percent }) => percent > 0 ? `${Math.round(percent * 100)}%` : ""} labelLine={false} {...anim}>
                  {comp.map((x) => <Cell key={x.key} fill={x.fill} />)}
                </Pie>
                <Tooltip {...tooltip} formatter={(v: number, n: string) => [`${v} (${compTotal ? Math.round((100 * v) / compTotal) : 0}%)`, n]} />
                <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 13 }} />
              </PieChart>
            </ResponsiveContainer>}
          table={<SimpleTable head={[t("st_category"), t("st_count"), "%"]}
            rows={comp.map((x) => [x.name, x.value, compTotal ? Math.round((100 * x.value) / compTotal) : 0])} />} />

        <ChartCard id="st-hist" title={t("st_hist_title", { metric: label(metric) })} subtitle={t("st_hist_hint")}
          chart={<ResponsiveContainer>
            <BarChart data={detail.histogram} margin={{ top: 8, right: 8, bottom: 0, left: -4 }} barCategoryGap={2}>
              <CartesianGrid vertical={false} stroke={c.grid} />
              <XAxis dataKey="bucket" {...axis} tickFormatter={(b) => `${b} ${t("st_h")}`} />
              <YAxis allowDecimals={false} {...axis} width={40} />
              <Tooltip {...tooltip} labelFormatter={(b) => `${b} ${t("st_h")}`} formatter={(v: number) => [v, label(metric)]} />
              <Bar dataKey="value" fill={c.series} radius={[4, 4, 0, 0]} {...anim} />
            </BarChart>
          </ResponsiveContainer>}
          table={<SimpleTable head={[t("st_hours"), label(metric)]} rows={detail.histogram.map((h) => [`${h.bucket} ${t("st_h")}`, h.value])} />} />

        <ChartCard id="st-bar" title={t("st_by_district", { metric: label(metric) })}
          chart={<ResponsiveContainer>
            <BarChart data={districts} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }} barCategoryGap={2}>
              <CartesianGrid horizontal={false} stroke={c.grid} />
              <XAxis type="number" allowDecimals={false} {...axis} />
              <YAxis type="category" dataKey="name" {...axis} width={150} interval={0} tick={{ fontSize: 11, fill: c.axis }} />
              <Tooltip {...tooltip} formatter={(v: number) => [v, label(metric)]} />
              <Bar dataKey="value" fill={c.series} radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 11, fill: c.axis }} {...anim} />
            </BarChart>
          </ResponsiveContainer>}
          table={<SimpleTable head={[t("district"), label(metric)]} rows={districts.map((d) => [d.name, d.value])} />} />
      </Box>}


    </Stack>
  );
}
