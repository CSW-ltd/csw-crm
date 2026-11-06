import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, ListItemText, MenuItem, Paper, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField } from "@mui/material";
import { adminApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { PasswordField } from "@/components/PasswordField";
import { useCan } from "@/hooks/useCan";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { confirmDialog, toast } from "@/lib/alerts";
import { isRoleActive } from "@/lib/session";
import { useAppSelector } from "@/store";
import type { AdminUser, Role } from "@/types";
import { AccessDialog } from "./AccessDialog";
import { type RefData } from "./AdminHome";

const ALL_ROLES: Role[] = ["admin", "manager", "operator", "gps", "legal", "accountant", "driver"];
const STAFF_ROLES: Role[] = ["operator", "gps", "legal", "driver"]; // manager boshqara oladigan rollar
const SINGLE: Role[] = ["driver", "gps"];        // bitta tuman
const MULTI: Role[] = ["manager", "legal", "operator", "accountant"]; // bir nechta tuman
type Form = { id?: number; username: string; full_name: string; phone: string; role: Role; district_id: number | ""; district_ids: number[]; password: string };
const EMPTY: Form = { username: "", full_name: "", phone: "", role: "driver", district_id: "", district_ids: [], password: "" };

export function UsersTab({ districts }: RefData) {
  const { t, tErr } = useI18n();
  const can = useCan();
  const me = useAppSelector((s) => s.auth.user);
  const isAdmin = me?.role === "admin";
  const roles = isAdmin ? ALL_ROLES : STAFF_ROLES;
  const formRoles = roles.filter(isRoleActive); // yangi xodim — faqat faol rollar (ACTIVE_ROLES)
  const newRole: Role = isAdmin ? "driver" : "gps";
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [role, setRole] = useState<Role | "">("");
  const [district, setDistrict] = useState<number | "">("");
  const [q, setQ] = useState("");
  const [form, setForm] = useState<Form | null>(null);
  const [reset, setReset] = useState<{ user: AdminUser; password: string } | null>(null);
  const [accessFor, setAccessFor] = useState<AdminUser | null>(null);
  const [busy, setBusy] = useState(false);
  const roleLabel = (r: Role) => t(`r_${r}` as MessageKey);
  const dName = (id: number) => districts.find((d) => d.id === id)?.name ?? `#${id}`;

  const load = useCallback(async () => setUsers(await adminApi.users()), []);
  useEffect(() => { load().catch(() => undefined); }, [load]);

  const shown = useMemo(() => users.filter((u) =>
    (!role || u.role === role) && (!district || u.district_ids.includes(district)) &&
    (!q || `${u.username} ${u.full_name} ${u.phone ?? ""}`.toLowerCase().includes(q.toLowerCase()))), [users, role, district, q]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true);
    try { await fn(); if (ok) toast(ok); await load(); return true; }
    catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); return false; }
    finally { setBusy(false); }
  };

  const save = async () => {
    if (!form) return;
    const single = SINGLE.includes(form.role), multi = MULTI.includes(form.role);
    const district_id = single && form.district_id !== "" ? form.district_id : null;
    const district_ids = multi ? form.district_ids : [];
    const done = await run(() => form.id
      ? adminApi.updateUser(form.id, { full_name: form.full_name, phone: form.phone || null, role: form.role, district_id, ...(multi ? { district_ids } : {}) })
      : adminApi.createUser({ username: form.username.trim().toLowerCase(), full_name: form.full_name, phone: form.phone || null, role: form.role,
        district_id, district_ids, password: form.password }),
    form.id || isAdmin ? t("saved") : t("sent_for_approval"));
    if (done) setForm(null);
  };

  const toggle = async (u: AdminUser) => {
    if (u.is_active && !(await confirmDialog(t("confirm_deactivate"), t("deactivate"), t("cancel"), u.full_name))) return;
    await run(() => adminApi.updateUser(u.id, { is_active: !u.is_active }), t("saved"));
  };

  const single = form ? SINGLE.includes(form.role) : false;
  const multi = form ? MULTI.includes(form.role) : false;
  const formValid = form && form.full_name.trim().length >= 2 && (!single || form.district_id !== "") &&
    (!multi || isAdmin || form.district_ids.length > 0) &&
    (form.id || (/^[a-z0-9_.]{3,50}$/.test(form.username.trim().toLowerCase()) && form.password.length >= 8));
  const activeDistricts = districts.filter((d) => d.is_active);

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField id="user-search" size="small" label={t("search")} value={q} onChange={(e) => setQ(e.target.value)} sx={{ flex: 1 }} />
        <TextField id="user-role" size="small" select label={t("role")} value={role} onChange={(e) => setRole(e.target.value as Role | "")} sx={{ minWidth: 190 }}>
          <MenuItem value="">{t("all")}</MenuItem>
          {roles.map((r) => <MenuItem key={r} value={r}>{roleLabel(r)}</MenuItem>)}
        </TextField>
        <TextField id="user-district" size="small" select label={t("district")} value={district} onChange={(e) => setDistrict(e.target.value === "" ? "" : Number(e.target.value))} sx={{ minWidth: 190 }}>
          <MenuItem value="">{t("all")}</MenuItem>
          {districts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
        </TextField>
        {can("staff.create") && <Button variant="contained" sx={{ whiteSpace: "nowrap" }}
          onClick={() => setForm({ ...EMPTY, role: formRoles.includes(newRole) ? newRole : formRoles[0] })}>{t("new_user")}</Button>}
      </Stack>
      <TableContainer>
        <Table size="small">
          <TableHead><TableRow>
            <TableCell>{t("username")}</TableCell><TableCell>{t("full_name")}</TableCell><TableCell>{t("role")}</TableCell>
            <TableCell>{t("district")}</TableCell><TableCell>{t("status")}</TableCell><TableCell />
          </TableRow></TableHead>
          <TableBody>
            {shown.map((u) => (
              <TableRow key={u.id} data-username={u.username} sx={{ opacity: u.is_active || u.approval_status === "pending" ? 1 : 0.55 }}>
                <TableCell sx={{ fontFamily: "monospace" }}>{u.username}</TableCell>
                <TableCell>{u.full_name}{u.phone && <><br /><small>{u.phone}</small></>}</TableCell>
                <TableCell>{roleLabel(u.role)}</TableCell>
                <TableCell sx={{ maxWidth: 220 }}>
                  {u.district_ids.length === 0 ? "—" : u.district_ids.length > 3 && u.district_ids.length === districts.length
                    ? t("all_districts_count", { n: u.district_ids.length }) : u.district_ids.map(dName).join(", ")}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {u.approval_status === "pending" ? <Chip size="small" color="warning" label={t("pending_approval")} />
                      : u.approval_status === "rejected" ? <Chip size="small" label={t("rejected")} />
                      : <Chip size="small" color={u.is_active ? "success" : "default"} label={t(u.is_active ? "active" : "inactive")} />}
                    {u.locked_until && new Date(u.locked_until + "Z") > new Date() && <Chip size="small" color="error" label={t("locked")} />}
                    {u.must_change_password && u.approval_status === "approved" && <Chip size="small" color="warning" variant="outlined" label={t("temp_password_pending")} />}
                  </Stack>
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  {isAdmin && u.approval_status === "pending" && <>
                    <Button size="small" variant="contained" disableElevation disabled={busy} onClick={() => run(() => adminApi.approveUser(u.id), t("saved"))}>{t("approve")}</Button>
                    <Button size="small" color="error" disabled={busy} onClick={() => run(() => adminApi.rejectUser(u.id), t("saved"))}>{t("reject")}</Button>
                  </>}
                  {can("staff.edit") && <Button size="small" onClick={() => setForm({ id: u.id, username: u.username, full_name: u.full_name, phone: u.phone ?? "",
                    role: u.role, district_id: u.district_id ?? "", district_ids: MULTI.includes(u.role) ? u.district_ids : [], password: "" })}>{t("edit")}</Button>}
                  {can("staff.view") && u.role !== "admin" && u.id !== me?.id && <Button size="small" onClick={() => setAccessFor(u)}>{t("access")}</Button>}
                  {can("staff.reset_password") && u.approval_status === "approved" && <Button size="small" onClick={() => setReset({ user: u, password: "" })}>{t("reset_password")}</Button>}
                  {can("staff.deactivate") && u.id !== me?.id && u.approval_status === "approved" &&
                    <Button size="small" color={u.is_active ? "error" : "success"} disabled={busy} onClick={() => toggle(u)}>{t(u.is_active ? "deactivate" : "activate")}</Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={!!form} onClose={() => setForm(null)} fullWidth maxWidth="sm">
        <DialogTitle>{form?.id ? t("edit") : t("new_user")}</DialogTitle>
        {form && <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField id="f-username" label={t("username")} value={form.username} disabled={!!form.id} helperText={t("username_hint")}
              onChange={(e) => setForm({ ...form, username: e.target.value })} autoCapitalize="none" />
            <TextField id="f-fullname" label={t("full_name")} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            <TextField id="f-phone" label={t("phone")} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+998 90 123-45-67" />
            <TextField id="f-role" select label={t("role")} value={form.role} disabled={form.id === me?.id}
              onChange={(e) => setForm({ ...form, role: e.target.value as Role, district_id: "", district_ids: [] })}>
              {(formRoles.includes(form.role) ? formRoles : [...formRoles, form.role]).map((r) => <MenuItem key={r} value={r}>{roleLabel(r)}</MenuItem>)}
            </TextField>
            {single && <TextField id="f-district" select label={t("district")} value={form.district_id} required
              onChange={(e) => setForm({ ...form, district_id: Number(e.target.value) })}>
              {activeDistricts.map((d) => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </TextField>}
            {multi && <TextField id="f-districts" select label={t("districts_many")} value={form.district_ids} required={!isAdmin}
              SelectProps={{ multiple: true, renderValue: (v) => (v as number[]).map(dName).join(", ") }}
              onChange={(e) => setForm({ ...form, district_ids: (e.target.value as unknown as number[]) })}>
              {activeDistricts.map((d) => <MenuItem key={d.id} value={d.id}>
                <Checkbox size="small" checked={form.district_ids.includes(d.id)} /><ListItemText primary={d.name} />
              </MenuItem>)}
            </TextField>}
            {!form.id && <PasswordField defaultVisible id="f-password" label={t("temp_password")} value={form.password} helperText={t("temp_password_hint")}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />}
          </Stack>
        </DialogContent>}
        <DialogActions>
          <Button onClick={() => setForm(null)}>{t("cancel")}</Button>
          <Button variant="contained" onClick={save} disabled={busy || !formValid}>{t("save")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!reset} onClose={() => setReset(null)} fullWidth maxWidth="xs">
        <DialogTitle>{t("reset_password")}: {reset?.user.username}</DialogTitle>
        <DialogContent>
          <PasswordField defaultVisible id="reset-password" sx={{ mt: 1 }} fullWidth label={t("temp_password")} helperText={t("temp_password_hint")}
            value={reset?.password ?? ""} onChange={(e) => reset && setReset({ ...reset, password: e.target.value })} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReset(null)}>{t("cancel")}</Button>
          <Button variant="contained" disabled={busy || (reset?.password.length ?? 0) < 8}
            onClick={async () => { if (reset && await run(() => adminApi.resetPassword(reset.user.id, reset.password), t("saved"))) setReset(null); }}>{t("save")}</Button>
        </DialogActions>
      </Dialog>

      {accessFor && <AccessDialog user={accessFor} districts={districts} onClose={() => setAccessFor(null)} onSaved={() => load()} />}
    </Paper>
  );
}
