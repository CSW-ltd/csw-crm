import { useState } from "react";
import { Alert, Box, Button, Chip, Stack, TextField, Typography } from "@mui/material";
import { Navigate } from "react-router-dom";
import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { useOnline } from "@/hooks/useOnline";
import { useI18n } from "@/i18n/I18nContext";
import type { MessageKey } from "@/i18n/messages";
import { afterLoginPath } from "@/lib/routes";
import { lastPath } from "@/hooks/usePersisted";
import { getDemoAccounts, getPortal, isDemo, isTabMode, portalRole } from "@/lib/session";
import { useAppDispatch, useAppSelector } from "@/store";
import { login } from "@/store/authSlice";


export function LoginPage() {
  const { t, tErr } = useI18n();
  const dispatch = useAppDispatch();
  const online = useOnline();
  const { user, error, errorHome } = useAppSelector((s) => s.auth);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [caps, setCaps] = useState(false);
  const [touched, setTouched] = useState(false);

  if (user) return <Navigate to={afterLoginPath(user, lastPath())} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!username.trim() || !password) return;
    setBusy(true);
    await dispatch(login({ username: username.trim(), password }));
    setBusy(false);
  };
  const capsCheck = (e: React.KeyboardEvent) => setCaps(e.getModifierState?.("CapsLock") ?? false);
  const portal = getPortal();
  const unknownPortal = portal !== null && portal.roles.length === 0;
  const role = portalRole();

  return (
    <AuthShell steps={[t("auth_step_1"), t("auth_step_2"), t("auth_step_3")]}>
      <Box component="form" onSubmit={submit} noValidate>
        {role && <Chip size="small" color="primary" variant="outlined" sx={{ mb: 1.5, fontWeight: 600 }}
          label={t(`portal_${role}` as MessageKey)} />}
        <Typography component="h1" sx={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.2 }}>{t("login_title")}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>{t("login_subtitle")}</Typography>
        <Stack spacing={2}>
          {!online && <Alert severity="warning">{t("offline")}</Alert>}
          {unknownPortal && <Alert severity="error">{t("err_unknown_portal")}</Alert>}
          <TextField id="username" label={t("username")} value={username} onChange={(e) => setUsername(e.target.value)}
            autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus fullWidth
            error={touched && !username.trim()} helperText={touched && !username.trim() ? t("field_required") : t("username_help")} />
          <PasswordField id="password" label={t("password")} value={password} onChange={(e) => setPassword(e.target.value)}
            onKeyUp={capsCheck} onKeyDown={capsCheck} autoComplete="current-password" fullWidth
            error={touched && !password} helperText={caps ? t("caps_lock_on") : touched && !password ? t("field_required") : " "}
            FormHelperTextProps={{ sx: caps ? { color: "warning.main", fontWeight: 600 } : undefined }} />
          {error && <Alert severity="error" variant="outlined" id="login-error">
            {tErr(error)}
            {error === "wrong_portal" && errorHome && <>{" "}{t("wrong_portal_go")}{" "}
              <a href={`https://${errorHome}/login`}>{errorHome}</a></>}
          </Alert>}
          <Button type="submit" variant="contained" size="large" fullWidth disableElevation disabled={busy || !online || unknownPortal}>
            {busy ? t("signing_in") : t("sign_in")}
          </Button>
          <Typography variant="body2" color="text.secondary">{t("forgot_password_hint")}</Typography>
        </Stack>

        {isDemo() && getDemoAccounts().length > 0 && <Box sx={{ mt: 4, pt: 3, borderTop: 1, borderColor: "divider" }}>
          <Typography variant="body2" fontWeight={600}>{t("demo_accounts")}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>
            {t(isTabMode() ? "demo_accounts_hint_tabs" : "demo_accounts_hint")}
          </Typography>
          <Stack direction="row" useFlexGap flexWrap="wrap" gap={1}>
            {getDemoAccounts().map((a) => (
              <Chip key={a.username} variant="outlined" clickable label={`${t(`r_${a.role}` as MessageKey)}: ${a.username}`}
                onClick={() => { setUsername(a.username); setPassword(""); setTouched(false); }} />
            ))}
          </Stack>
        </Box>}
      </Box>
    </AuthShell>
  );
}
