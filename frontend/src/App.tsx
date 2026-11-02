import { useEffect, type ReactNode } from "react";
import { Alert, Box, CircularProgress } from "@mui/material";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { rememberPath } from "@/hooks/usePersisted";
import { DriverLayout } from "@/components/DriverLayout";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { closeSocket, getSocket } from "@/lib/socket";
import { LoginPage } from "@/pages/LoginPage";
import { ActPage } from "@/pages/driver/ActPage";
import { DriverHome } from "@/pages/driver/DriverHome";
import { GpsHome } from "@/pages/gps/GpsHome";
import { OperatorHome } from "@/pages/operator/OperatorHome";
import { AdminHome } from "@/pages/admin/AdminHome";
import { CompanyPage } from "@/pages/admin/CompanyPage";
import { ChangePasswordPage } from "@/pages/ChangePasswordPage";
import { afterLoginPath } from "@/lib/routes";
import { lastPath } from "@/hooks/usePersisted";
import { useAppDispatch, useAppSelector } from "@/store";
import { loadMe, sessionExpired } from "@/store/authSlice";
import { refreshDriver } from "@/store/driverSlice";
import type { Role } from "@/types";

function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, status } = useAppSelector((s) => s.auth);
  if (status !== "ready") return <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}><CircularProgress /></Box>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (!roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** Haydovchi bo'limi: holatni yuklaydi va Socket.IO orqali yangilanib turadi. */
function DriverSection({ children }: { children: ReactNode }) {
  const dispatch = useAppDispatch();
  useEffect(() => {
    dispatch(refreshDriver());
    const s = getSocket();
    const onUpdate = () => dispatch(refreshDriver());
    s.on("request:updated", onUpdate);
    s.on("connect", onUpdate); // qayta ulanganda o'tkazib yuborilganlarni olish
    return () => { s.off("request:updated", onUpdate); s.off("connect", onUpdate); closeSocket(); };
  }, [dispatch]);
  return <DriverLayout>{children}</DriverLayout>;
}

/** Har sahifa almashganda oxirgi yo'l (+ #tab) eslab qolinadi — refresh yoki qayta kirishdan keyin o'sha sahifa ochiladi. */
function PathMemory() {
  const loc = useLocation();
  useEffect(() => { rememberPath(loc.pathname + loc.search + loc.hash); }, [loc.pathname, loc.search, loc.hash]);
  return null;
}

function Home() {
  const user = useAppSelector((s) => s.auth.user);
  const status = useAppSelector((s) => s.auth.status);
  if (status !== "ready") return null;
  if (!user) return <Navigate to="/login" replace />;
  const home = afterLoginPath(user, lastPath());
  if (home !== "/") return <Navigate to={home} replace />;
  return <Alert severity="info" sx={{ m: 2 }}>Bu rol uchun panel keyingi bosqichda qo'shiladi ({user.role}).</Alert>;
}

export function App() {
  const dispatch = useAppDispatch();
  const { t } = useI18n();
  useEffect(() => {
    dispatch(loadMe());
    const onLogout = () => dispatch(sessionExpired());
    window.addEventListener("csw:logout", onLogout);
    return () => window.removeEventListener("csw:logout", onLogout);
  }, [dispatch]);
  // Tab sarlavhasi: qaysi rolda va kim bo'lib kirilgani — bir nechta tabda turli rollarni ajratish uchun
  const me = useAppSelector((st) => st.auth.user);
  useEffect(() => {
    document.title = me ? `${t(`r_${me.role}` as MessageKey)} · ${me.full_name} — CSW` : `${t("login_title")} — CSW`;
  }, [t, me]);

  return (
    <BrowserRouter>
      <PathMemory />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/driver" element={<RequireRole roles={["driver"]}><DriverSection><DriverHome /></DriverSection></RequireRole>} />
        <Route path="/driver/requests/:id" element={<RequireRole roles={["driver"]}><DriverSection><ActPage /></DriverSection></RequireRole>} />
        <Route path="/gps" element={<RequireRole roles={["gps"]}><DriverLayout><GpsHome /></DriverLayout></RequireRole>} />
        <Route path="/admin" element={<RequireRole roles={["admin", "manager", "legal", "accountant"]}><DriverLayout wide><AdminHome /></DriverLayout></RequireRole>} />
        <Route path="/admin/korxona/:id/:view?" element={<RequireRole roles={["admin", "manager", "legal", "accountant"]}><DriverLayout wide><CompanyPage /></DriverLayout></RequireRole>} />
        <Route path="/operator" element={<RequireRole roles={["operator"]}><DriverLayout wide><OperatorHome /></DriverLayout></RequireRole>} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}
