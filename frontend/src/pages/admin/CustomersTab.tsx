import { useCallback, useEffect, useState } from "react";
import { Button, Chip, FormControlLabel, MenuItem, Paper, Stack, Switch, Table, TableBody, TableCell, TableContainer, TableHead,
  TablePagination, TableRow, TextField, Typography } from "@mui/material";
import { customersApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { useCan } from "@/hooks/useCan";
import type { CustomerListItem, LocationStatus } from "@/types";
import { districtLabel, type RefData } from "./AdminHome";
import { CustomerDialog } from "./CustomerDialog";
import { ImportDialog } from "./ImportDialog";
import { usePersisted } from "@/hooks/usePersisted";

const LOC_COLOR = { none: "default", pending: "warning", confirmed: "success" } as const;

export function MissingChips({ missing }: { missing: string[] }) {
  const { t } = useI18n();
  if (!missing.length) return <Chip size="small" color="success" variant="outlined" label={t("ready")} />;
  return <Stack direction="row" spacing={0.5}>
    {missing.map((m) => <Chip key={m} size="small" color="error" variant="outlined" label={t(m === "stir" ? "missing_stir" : "missing_contract")} />)}
  </Stack>;
}

export function LocationChip({ status }: { status: LocationStatus }) {
  const { t } = useI18n();
  return <Chip size="small" color={LOC_COLOR[status]} label={t(`loc_${status}`)} />;
}

/** Ko'rish: admin, manager, yurist. Karta/shartnoma: admin, yurist. Koordinata tasdig'i: admin, manager. Import: admin. */
export function CustomersTab({ districts, hideActions }: RefData & { hideActions?: boolean }) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const canEdit = can("customers.create");
  const canImport = can("customers.import");
  const [items, setItems] = useState<CustomerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [district, setDistrict] = usePersisted<number | "">("cust.district", "");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [incomplete, setIncomplete] = useState(false);
  const [loc, setLoc] = useState<LocationStatus | "">("");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState(25);
  const [openId, setOpenId] = useState<number | "new" | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  // Qidiruv maydoni: yozib bo'lgach 350 ms kutib so'rov yuboriladi
  useEffect(() => { const h = setTimeout(() => { setQuery(q.trim()); setPage(0); }, 350); return () => clearTimeout(h); }, [q]);

  const load = useCallback(async () => {
    try {
      const res = await customersApi.search({ district_id: district || undefined, q: query || undefined, incomplete: incomplete || undefined,
        location: loc || undefined, limit: rows, offset: page * rows });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
  }, [district, query, incomplete, loc, page, rows, tErr]);
  useEffect(() => { load(); }, [load]);

  const resetPage = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(0); };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2 }} alignItems={{ md: "center" }}>
        <TextField id="c-q" size="small" label={t("search")} value={q} onChange={(e) => setQ(e.target.value)} sx={{ minWidth: 240 }}
          placeholder={`${t("customer_name")}, ${t("stir")}, ${t("phone")}`} />
        <TextField id="c-district" size="small" select label={t("district")} value={district} sx={{ minWidth: 200 }}
          onChange={(e) => resetPage(setDistrict)(e.target.value === "" ? "" : Number(e.target.value))}>
          <MenuItem value="">{t("all")}</MenuItem>
          {districts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
        </TextField>
        <TextField id="c-loc" size="small" select label={t("location")} value={loc} sx={{ minWidth: 190 }}
          onChange={(e) => resetPage(setLoc)(e.target.value as LocationStatus | "")}>
          <MenuItem value="">{t("all")}</MenuItem>
          {(["none", "pending", "confirmed"] as const).map((s) => <MenuItem key={s} value={s}>{t(`loc_${s}`)}</MenuItem>)}
        </TextField>
        <FormControlLabel control={<Switch id="c-incomplete" checked={incomplete} onChange={(e) => resetPage(setIncomplete)(e.target.checked)} />}
          label={t("only_incomplete")} />
        <Stack direction="row" spacing={1} sx={{ ml: { md: "auto" }, "& .MuiButton-root": { whiteSpace: "nowrap" } }}>
          {!hideActions && canImport && <Button variant="outlined" onClick={() => setImportOpen(true)}>{t("import_excel")}</Button>}
          {!hideActions && canEdit && <Button variant="contained" onClick={() => setOpenId("new")}>{t("new_contract")}</Button>}
        </Stack>
      </Stack>

      <TableContainer>
        <Table size="small">
          <TableHead><TableRow>
            <TableCell>№</TableCell><TableCell>{t("customer_name")}</TableCell><TableCell>{t("district")}</TableCell>
            <TableCell>{t("stir")}</TableCell><TableCell>{t("phone")}</TableCell><TableCell>{t("status")}</TableCell><TableCell>{t("location")}</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {items.map((c) => (
              <TableRow key={c.id} hover sx={{ cursor: "pointer" }} onClick={() => setOpenId(c.id)}>
                <TableCell sx={{ fontFamily: "monospace", whiteSpace: "nowrap" }}>{c.fixed_no}</TableCell>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>{c.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{[c.activity_type, c.address].filter(Boolean).join(" · ") || "—"}</Typography>
                </TableCell>
                <TableCell>{districtLabel(districts, c.district_id)}</TableCell>
                <TableCell sx={{ fontFamily: "monospace" }}>{c.stir ?? "—"}</TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{c.phone ?? "—"}{c.contacts_count > 1 && <Typography component="span" variant="caption" color="text.secondary"> +{c.contacts_count - 1}</Typography>}</TableCell>
                <TableCell><MissingChips missing={c.missing_fields} /></TableCell>
                <TableCell><LocationChip status={c.location_status} /></TableCell>
              </TableRow>
            ))}
            {!items.length && <TableRow><TableCell colSpan={7} align="center" sx={{ color: "text.secondary", py: 4 }}>—</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination component="div" count={total} page={page} rowsPerPage={rows} rowsPerPageOptions={[25, 50, 100]}
        onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setRows(Number(e.target.value)); setPage(0); }}
        labelRowsPerPage="" labelDisplayedRows={({ from, to, count }) => `${from}–${to} / ${count}`} />

      {openId !== null && <CustomerDialog id={openId} districts={districts} onClose={() => setOpenId(null)}
        onChanged={(id) => { load(); if (openId === "new") setOpenId(id); }} />}
      {importOpen && <ImportDialog onClose={() => setImportOpen(false)} onImported={() => { setPage(0); load(); }} />}
    </Paper>
  );
}
