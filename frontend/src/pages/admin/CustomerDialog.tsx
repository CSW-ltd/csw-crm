import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Link, MenuItem, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { customersApi, type ContractCreate } from "@/api/endpoints";
import { onlyDigits } from "@/components/DigitsField";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";
import { useCan } from "@/hooks/useCan";
import type { ContractType, CustomerDetail, District } from "@/types";
import { LocationChip, MissingChips } from "./CustomersTab";
import { StatusChip } from "./ContractWizard";

const CONTRACT_TYPES: ContractType[] = ["per_trip", "by_volume", "monthly", "one_off"];
type Card = { name: string; district_id: number | ""; stir: string; director: string; phone: string; address: string; activity_type: string };
const today = () => new Date().toISOString().slice(0, 10);
const inForce = (c: { is_active: boolean; valid_from: string; valid_to: string }) => c.is_active && c.valid_from <= today() && today() <= c.valid_to;

interface Props { id: number | "new"; districts: District[]; onClose: () => void; onChanged: (id: number) => void }

export function CustomerDialog({ id, districts, onClose, onChanged }: Props) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const canEdit = can("customers.edit") || (id === "new" && can("customers.create"));
  const canContract = can("customers.contract");
  const canConfirm = can("customers.location_confirm");
  const [cust, setCust] = useState<CustomerDetail | null>(null);
  const [card, setCard] = useState<Card>({ name: "", district_id: "", stir: "", director: "", phone: "", address: "", activity_type: "" });
  const [contact, setContact] = useState({ name: "", phone: "" });
  const [contract, setContract] = useState<ContractCreate | null>(null);
  const [manual, setManual] = useState<{ lat: string; lng: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const fill = useCallback((c: CustomerDetail) => {
    setCust(c);
    setCard({ name: c.name, district_id: c.district_id, stir: c.stir ?? "", director: c.director ?? "", phone: c.phone ?? "",
      address: c.address ?? "", activity_type: c.activity_type ?? "" });
  }, []);
  useEffect(() => {
    if (id !== "new") customersApi.get(id).then(fill).catch((e) => toast(tErr(errorCode(e), errorMessage(e)), "error"));
  }, [id, fill, tErr]);

  const run = async (fn: () => Promise<CustomerDetail>) => {
    setBusy(true);
    try { const c = await fn(); fill(c); toast(t("saved")); onChanged(c.id); return true; }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); return false; }
    finally { setBusy(false); }
  };
  const opt = (v: string) => v.trim() || null;
  const saveCard = () => run(() => cust
    ? customersApi.update(cust.id, { name: card.name.trim(), stir: opt(card.stir), director: opt(card.director), phone: opt(card.phone),
        address: opt(card.address), activity_type: opt(card.activity_type) })
    : customersApi.create({ name: card.name.trim(), district_id: card.district_id as number, stir: opt(card.stir), director: opt(card.director),
        phone: opt(card.phone), address: opt(card.address), activity_type: opt(card.activity_type) }));
  const stirBad = card.stir !== "" && !/^\d{9}$/.test(card.stir);
  const field = (k: keyof Card, label: string, extra?: object) => (
    <TextField id={`cu-${k}`} size="small" label={label} value={card[k]} disabled={!canEdit}
      onChange={(e) => setCard({ ...card, [k]: k === "stir" ? onlyDigits(e.target.value, 9) : e.target.value })} {...extra} />
  );

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
        {cust ? <><Box component="span" sx={{ fontFamily: "monospace" }}>{cust.fixed_no}</Box> {cust.name}</> : t("new_customer")}
        {cust && <Box sx={{ ml: "auto", display: "flex", gap: 1 }}><MissingChips missing={cust.missing_fields} />
          <Chip size="small" variant="outlined" label={t(cust.source === "excel" ? "source_excel" : "source_manual")} /></Box>}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          {cust && cust.missing_fields.length > 0 && <Alert severity="warning">{t("cannot_assign_hint")}</Alert>}

          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            {field("name", t("customer_name"), { sx: { gridColumn: { sm: "1 / -1" } } })}
            <TextField id="cu-district" size="small" select label={t("district")} value={card.district_id} disabled={!!cust || !canEdit}
              onChange={(e) => setCard({ ...card, district_id: Number(e.target.value) })}>
              {districts.filter((d) => d.is_active || d.id === card.district_id).map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </TextField>
            {field("stir", t("stir"), { error: stirBad, helperText: stirBad ? "9" : undefined, inputProps: { inputMode: "numeric", maxLength: 9 } })}
            {field("director", t("director"))}
            {field("activity_type", t("activity_type"))}
            {field("phone", t("phone"), { placeholder: "94 512 11 16" })}
            {field("address", t("address"))}
          </Box>
          {canEdit && <Box><Button variant="contained" onClick={saveCard}
            disabled={busy || card.name.trim().length < 2 || card.district_id === "" || stirBad}>{t("save")}</Button></Box>}

          {cust && <>
            <Divider />
            <Box>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>{t("contacts")}</Typography>
              {cust.contacts.length ? <Table size="small"><TableBody>
                {cust.contacts.map((c) => <TableRow key={c.id}><TableCell sx={{ whiteSpace: "nowrap" }}>{c.phone}</TableCell><TableCell>{c.name ?? "—"}</TableCell></TableRow>)}
              </TableBody></Table> : <Typography color="text.secondary">—</Typography>}
              {canEdit && <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1 }}>
                <TextField id="ct-phone" size="small" label={t("phone")} value={contact.phone} placeholder="94 512 11 16" onChange={(e) => setContact({ ...contact, phone: e.target.value })} />
                <TextField id="ct-name" size="small" label={t("contact_name")} value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} />
                <Button disabled={busy || !contact.phone.trim()} onClick={async () => {
                  if (await run(() => customersApi.addContact(cust.id, { phone: contact.phone, name: opt(contact.name) }))) setContact({ name: "", phone: "" });
                }}>{t("add_contact")}</Button>
              </Stack>}
            </Box>

            <Divider />
            <Box>
              <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="subtitle1" fontWeight={600}>{t("contracts")}</Typography>
                {canContract && !contract && <Button sx={{ ml: "auto" }} onClick={() => setContract({ number: "", type: "monthly", signed_on: today(), price: null,
                  valid_from: today(), valid_to: `${new Date().getFullYear()}-12-31` })}>{t("add_contract")}</Button>}
              </Stack>
              {cust.contracts.length ? <Table size="small">
                <TableHead><TableRow><TableCell>{t("contract_no")}</TableCell><TableCell>{t("contract_type")}</TableCell><TableCell>{t("valid_from")}</TableCell>
                  <TableCell>{t("valid_to")}</TableCell><TableCell>{t("price")}</TableCell><TableCell>{t("status")}</TableCell></TableRow></TableHead>
                <TableBody>{cust.contracts.map((c) => <TableRow key={c.id}>
                  <TableCell sx={{ fontFamily: "monospace" }}>{c.display_number ?? c.number}</TableCell><TableCell>{t(`ct_${c.type}`)}</TableCell>
                  <TableCell>{c.valid_from}</TableCell><TableCell>{c.valid_to}</TableCell><TableCell>{c.price ?? "—"}</TableCell>
                  <TableCell>{c.status && c.status !== "approved" ? <StatusChip status={c.status} />
                    : <Chip size="small" color={inForce(c) ? "success" : "default"} label={t(inForce(c) ? "in_force" : "expired")} />}</TableCell>
                </TableRow>)}</TableBody>
              </Table> : <Typography color="text.secondary">—</Typography>}
              {contract && <Box sx={{ mt: 1.5, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" } }}>
                <TextField id="k-number" size="small" label={t("contract_no")} value={contract.number} onChange={(e) => setContract({ ...contract, number: e.target.value })} />
                <TextField id="k-type" size="small" select label={t("contract_type")} value={contract.type} onChange={(e) => setContract({ ...contract, type: e.target.value as ContractType })}>
                  {CONTRACT_TYPES.map((ct) => <MenuItem key={ct} value={ct}>{t(`ct_${ct}`)}</MenuItem>)}
                </TextField>
                <TextField id="k-price" size="small" type="number" label={t("price")} value={contract.price ?? ""} onChange={(e) => setContract({ ...contract, price: e.target.value === "" ? null : Number(e.target.value) })} />
                <TextField id="k-signed" size="small" type="date" label={t("signed_on")} value={contract.signed_on ?? ""} InputLabelProps={{ shrink: true }} onChange={(e) => setContract({ ...contract, signed_on: e.target.value || null })} />
                <TextField id="k-from" size="small" type="date" label={t("valid_from")} value={contract.valid_from} InputLabelProps={{ shrink: true }} onChange={(e) => setContract({ ...contract, valid_from: e.target.value })} />
                <TextField id="k-to" size="small" type="date" label={t("valid_to")} value={contract.valid_to} InputLabelProps={{ shrink: true }} onChange={(e) => setContract({ ...contract, valid_to: e.target.value })} />
                <Stack direction="row" spacing={1} sx={{ gridColumn: { sm: "1 / -1" } }}>
                  <Button variant="contained" disabled={busy || !contract.number.trim() || !contract.valid_from || !contract.valid_to}
                    onClick={async () => { if (await run(() => customersApi.addContract(cust.id, { ...contract, number: contract.number.trim() }))) setContract(null); }}>{t("save")}</Button>
                  <Button onClick={() => setContract(null)}>{t("cancel")}</Button>
                </Stack>
              </Box>}
            </Box>

            <Divider />
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="subtitle1" fontWeight={600}>{t("location")}</Typography>
                <LocationChip status={cust.location_status} />
                {cust.lat !== null && cust.lng !== null && <>
                  <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{cust.lat.toFixed(6)}, {cust.lng.toFixed(6)}</Typography>
                  <Link href={`https://www.google.com/maps?q=${cust.lat},${cust.lng}`} target="_blank" rel="noopener">{t("open_map")}</Link>
                </>}
              </Stack>
              {cust.location_status === "none" && <Typography variant="body2" color="text.secondary">{t("loc_hint_none")}</Typography>}
              {canConfirm && <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1 }}>
                {cust.location_status === "pending" && <Button variant="contained" color="success" disabled={busy}
                  onClick={() => run(() => customersApi.confirmLocation(cust.id))}>{t("confirm_location")}</Button>}
                {!manual ? <Button onClick={() => setManual({ lat: cust.lat?.toString() ?? "", lng: cust.lng?.toString() ?? "" })}>{t("set_location")}</Button> : <>
                  <TextField id="m-lat" size="small" label="lat" value={manual.lat} onChange={(e) => setManual({ ...manual, lat: e.target.value })} />
                  <TextField id="m-lng" size="small" label="lng" value={manual.lng} onChange={(e) => setManual({ ...manual, lng: e.target.value })} />
                  <Button variant="contained" disabled={busy || !manual.lat || !manual.lng}
                    onClick={async () => { if (await run(() => customersApi.confirmLocation(cust.id, { lat: Number(manual.lat), lng: Number(manual.lng) }))) setManual(null); }}>{t("save")}</Button>
                  <Button onClick={() => setManual(null)}>{t("cancel")}</Button>
                </>}
              </Stack>}
            </Box>
          </>}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>{t("close")}</Button></DialogActions>
    </Dialog>
  );
}
