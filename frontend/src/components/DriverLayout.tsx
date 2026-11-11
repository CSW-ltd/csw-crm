import type { ReactNode } from "react";
import { Alert, AppBar, Box, Button, Container, MenuItem, Select, Toolbar, Typography } from "@mui/material";
import { NotificationBell } from "@/components/NotificationBell";
import { SituationBell, SituationProvider } from "@/components/Situation";
import { useOnline } from "@/hooks/useOnline";
import { LANGS, useI18n, type Lang } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { useAppDispatch, useAppSelector } from "@/store";
import { logout } from "@/store/authSlice";

/** Har rol oynasining katta sarlavhasi va rangi — qaysi ish vazifasi bajarilayotgani darhol ko'rinsin. */
const ROLE_COLOR: Record<string, string> = { admin: "#263238", manager: "#1A4E8A", operator: "#6A1B9A", gps: "#B71C1C", legal: "#00796B",
  accountant: "#8D5B00", driver: "#2E7D32" };

export function DriverLayout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { t, lang, setLang } = useI18n();
  const online = useOnline();
  const user = useAppSelector((s) => s.auth.user);
  const plate = useAppSelector((s) => s.driver.today?.vehicle?.plate);
  const dispatch = useAppDispatch();
  // Vaziyat paneli: admin — hammasi; manager va buxgalter — o'z tumanlari
  const watcher = user?.role === "admin" || user?.role === "manager" || user?.role === "accountant";
  const page = (
    <Box sx={{ minHeight: "100%", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ gap: 1.5, flexWrap: "wrap" }}>
          <Typography variant="h6" color="primary" sx={{ fontWeight: 700, mr: "auto" }}>CSW</Typography>
          {watcher && <SituationBell />}
          {user && user.role !== "driver" && <NotificationBell />}
          <Typography variant="body2" color="text.secondary">{user?.full_name}{plate ? ` · ${plate}` : ""}</Typography>
          <Select size="small" value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label="Language">
            {LANGS.map((l) => <MenuItem key={l.id} value={l.id}>{l.label}</MenuItem>)}
          </Select>
          <Button onClick={() => dispatch(logout())}>{t("logout")}</Button>
        </Toolbar>
      </AppBar>
      {user && <Box id="role-banner" data-role={user.role} sx={{ bgcolor: ROLE_COLOR[user.role] ?? "#00A651", color: "#fff", px: { xs: 2, sm: 3 }, py: { xs: 1, sm: 1.25 } }}>
        <Container maxWidth={wide ? "lg" : "md"} disableGutters>
          <Typography sx={{ fontSize: { xs: 22, sm: 28 }, fontWeight: 800, lineHeight: 1.15, letterSpacing: 0.2 }}>{t(`rb_${user.role}` as MessageKey)}</Typography>
        </Container>
      </Box>}
      {!online && <Alert severity="warning" square>{t("offline")}</Alert>}
      <Container maxWidth={wide ? "lg" : "md"} sx={{ py: 2 }}>{children}</Container>
    </Box>
  );
  // Admin va manager: Vaziyat paneli hodisalari jonli keladi (qo'ng'iroqcha + popup)
  // Yozishma: o'qilmaganlar, jonli toast va yon panel — har bir rol uchun
  return watcher ? <SituationProvider>{page}</SituationProvider> : page;
}
