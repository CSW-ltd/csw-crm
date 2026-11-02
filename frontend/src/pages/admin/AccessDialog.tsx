import { useEffect, useState } from "react";
import { Alert, Box, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack,
  Typography } from "@mui/material";
import { adminApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { MESSAGES, type MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { useAppSelector } from "@/store";
import type { Access, AdminUser, District } from "@/types";

/**
 * Xodim huquqlari: bo'limlar × amallar jadvali va (manager/yurist/operator uchun) tumanlar.
 * Admin hammasini o'zgartiradi; manager faqat o'zida bor ruxsatlarni va o'z tumanlarini (boshqalari o'chirilgan holda ko'rinadi).
 */
export function AccessDialog({ user, districts, onClose, onSaved }: { user: AdminUser; districts: District[]; onClose: () => void; onSaved: () => void }) {
  const { t, tErr } = useI18n();
  const me = useAppSelector((s) => s.auth.user);
  const [modules, setModules] = useState<Record<string, string[]> | null>(null);
  const [acc, setAcc] = useState<Access | null>(null);
  const [perms, setPerms] = useState<Set<string>>(new Set());
  const [dists, setDists] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([adminApi.permissionCatalog(), adminApi.access(user.id)]).then(([c, a]) => {
      setModules(c.modules); setAcc(a); setPerms(new Set(a.permissions)); setDists(new Set(a.district_ids));
    }).catch((e) => toast(tErr(errorCode(e), errorMessage(e)), "error"));
  }, [user.id, tErr]);

  const grantable = new Set(acc?.grantable ?? []);
  const readOnly = !grantable.size || user.role === "admin" || user.id === me?.id;
  const assignable = acc?.assignable_district_ids;
  const toggle = (code: string) => setPerms((s) => { const n = new Set(s); if (n.has(code)) n.delete(code); else n.add(code); return n; });
  const toggleD = (id: number) => setDists((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const save = async () => {
    if (!acc) return;
    setBusy(true);
    try {
      await adminApi.saveAccess(user.id, { permissions: Array.from(perms), district_ids: acc.multi_district ? Array.from(dists) : undefined });
      toast(t("saved"));
      onSaved();
      onClose();
    } catch (e) { toast(tErr(errorCode(e), errorMessage(e)), "error"); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{t("access_title", { name: user.full_name })}</DialogTitle>
      <DialogContent dividers>
        {!acc || !modules ? <Stack alignItems="center" sx={{ py: 4 }}><CircularProgress /></Stack> : user.role === "admin"
          ? <Alert severity="info">{t("admin_has_all_hint")}</Alert>
          : <Stack spacing={2.5}>
            <Typography variant="body2" color="text.secondary">{t(me?.role === "admin" ? "access_hint_admin" : "access_hint_manager")}</Typography>
            {/* Har bo'lim — bitta qator: nomi va uning amallari (keng jadval o'rniga — gorizontal skrollsiz) */}
            <Box id="access-matrix" sx={{ border: 1, borderColor: "divider", borderRadius: 1 }}>
              {Object.entries(modules).map(([m, acts], i) => (
                <Box key={m} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "190px 1fr" }, gap: { xs: 0.5, sm: 2 }, alignItems: "center",
                  px: 2, py: 1.25, borderTop: i ? 1 : 0, borderColor: "divider" }}>
                  <Box>
                    <Typography fontWeight={600} data-module={m}>{t(`m_${m}` as MessageKey)}</Typography>
                    {`mh_${m}` in MESSAGES && <Typography variant="caption" color="text.secondary" display="block">{t(`mh_${m}` as MessageKey)}</Typography>}
                  </Box>
                  <Stack direction="row" flexWrap="wrap" useFlexGap columnGap={2}>
                    {acts.map((a) => {
                      const code = `${m}.${a}`;
                      return <FormControlLabel key={a} sx={{ mr: 0 }} label={<Typography variant="body2">{t((`a_${m}_${a}` in MESSAGES ? `a_${m}_${a}` : `a_${a}`) as MessageKey)}</Typography>}
                        control={<Checkbox size="small" checked={perms.has(code)} disabled={readOnly || !grantable.has(code)} onChange={() => toggle(code)}
                          inputProps={{ "aria-label": code, "data-code": code } as React.InputHTMLAttributes<HTMLInputElement>} />} />;
                    })}
                  </Stack>
                </Box>
              ))}
            </Box>
            <Box>
              <Typography variant="subtitle2" gutterBottom>{t("access_districts")}</Typography>
              {acc.multi_district
                ? <Box id="access-districts" sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" } }}>
                  {districts.filter((d) => assignable === null || assignable?.includes(d.id) || dists.has(d.id)).map((d) => (
                    <FormControlLabel key={d.id} label={d.name} control={<Checkbox size="small" checked={dists.has(d.id)} onChange={() => toggleD(d.id)}
                      disabled={readOnly || (assignable !== null && !assignable?.includes(d.id))} />} />
                  ))}
                </Box>
                : <Typography variant="body2" color="text.secondary">{t("access_single_district")}</Typography>}
            </Box>
          </Stack>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("cancel")}</Button>
        {!readOnly && <Button id="access-save" variant="contained" onClick={save} disabled={busy}>{t("save")}</Button>}
      </DialogActions>
    </Dialog>
  );
}
