import { useEffect, useState } from "react";
import { Alert, Box, Button, Checkbox, CircularProgress, FormControlLabel, Link, Stack, TextField, Typography } from "@mui/material";
import { authApi } from "@/api/endpoints";
import { errorCode } from "@/api/client";
import { DigitsField } from "@/components/DigitsField";
import { useI18n } from "@/i18n/I18nContext";
import { useAppDispatch } from "@/store";
import { mfaDone, type MfaChallenge } from "@/store/authSlice";
import type { User } from "@/types";

/** Bu xatolarda mfa_token yaroqsiz — login formasiga qaytiladi. */
const RESTART = new Set(["mfa_expired", "mfa_already_enabled", "mfa_setup_required", "account_locked"]);

const title = { fontSize: 28, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.2 } as const;

/** Admin 2FA: paroldan keyingi qadam. setup — QR + kod + zaxira kodlar; verify — ilova kodi yoki zaxira kod. */
export function MfaStep({ challenge }: { challenge: MfaChallenge }) {
  const { t, tErr } = useI18n();
  const dispatch = useAppDispatch();
  const [setup, setSetup] = useState<{ secret: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [backupMode, setBackupMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ user: User; codes: string[] } | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (challenge.mode !== "setup") return;
    authApi.mfaSetup(challenge.token).then(setSetup).catch((e) => setError(errorCode(e)));
  }, [challenge]);

  const back = () => dispatch(mfaDone(null));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (challenge.mode === "setup") {
        const r = await authApi.mfaEnable(challenge.token, code);
        setDone({ user: r.user, codes: r.backup_codes });
      } else {
        dispatch(mfaDone(await authApi.mfaVerify(challenge.token, code)));
      }
    } catch (err) {
      setError(errorCode(err));
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  const restart = error !== null && RESTART.has(error);
  const errorBox = error && <Alert severity="error" variant="outlined">
    {tErr(error)}{restart && <>{" "}<Link component="button" type="button" onClick={back}>{t("mfa_back_to_login")}</Link></>}
  </Alert>;

  // 3) Zaxira kodlar — sessiya allaqachon ochilgan, «Saqlab oldim»dan keyin panelga o'tiladi
  if (done) {
    const text = done.codes.join("\n");
    const download = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([`CSW — ${done.user.username}\n\n${text}\n`], { type: "text/plain" }));
      a.download = `csw-zaxira-kodlar-${done.user.username}.txt`;
      a.click();
      URL.revokeObjectURL(a.href);
    };
    return (
      <Box>
        <Typography component="h1" sx={title}>{t("mfa_backup_title")}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, mb: 2 }}>{t("mfa_backup_hint")}</Typography>
        <Box component="pre" id="mfa-backup-codes" sx={{ m: 0, p: 2, borderRadius: 1, bgcolor: "action.hover", fontFamily: "monospace",
          fontSize: 16, columns: 2, lineHeight: 1.9 }}>{text}</Box>
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          <Button variant="outlined" onClick={() => navigator.clipboard?.writeText(text)}>{t("copy")}</Button>
          <Button variant="outlined" onClick={download}>{t("mfa_download")}</Button>
        </Stack>
        <FormControlLabel sx={{ mt: 2 }} control={<Checkbox checked={saved} onChange={(e) => setSaved(e.target.checked)} />}
          label={t("mfa_saved_check")} />
        <Button variant="contained" size="large" fullWidth disableElevation sx={{ mt: 1 }} disabled={!saved}
          onClick={() => dispatch(mfaDone(done.user))}>{t("mfa_continue")}</Button>
      </Box>
    );
  }

  const codeField = backupMode
    ? <TextField id="mfa-code" label={t("mfa_backup_code")} value={code} onChange={(e) => setCode(e.target.value.slice(0, 20))}
        autoComplete="off" autoCapitalize="none" spellCheck={false} autoFocus fullWidth helperText={t("mfa_backup_code_help")} />
    : <DigitsField id="mfa-code" label={t("mfa_code")} max={6} value={code} onValue={setCode} autoFocus fullWidth
        autoComplete="one-time-code" inputProps={{ style: { fontSize: 22, letterSpacing: "0.3em" } }} />;

  // 1) Birinchi marta: QR kod
  if (challenge.mode === "setup") {
    return (
      <Box component="form" onSubmit={submit} noValidate>
        <Typography component="h1" sx={title}>{t("mfa_setup_title")}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, mb: 2 }}>{t("mfa_setup_subtitle")}</Typography>
        <Stack spacing={2}>
          <Typography variant="body2">1. {t("mfa_setup_step1")}</Typography>
          <Typography variant="body2">2. {t("mfa_setup_step2")}</Typography>
          {setup ? <>
            <Box component="img" alt="QR" src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
              sx={{ width: 200, height: 200, alignSelf: "center", imageRendering: "pixelated" }} />
            <Box>
              <Typography variant="caption" color="text.secondary">{t("mfa_manual_key")}</Typography>
              <Typography id="mfa-secret" sx={{ fontFamily: "monospace", wordBreak: "break-all", userSelect: "all" }}>
                {setup.secret.match(/.{1,4}/g)?.join(" ")}
              </Typography>
            </Box>
          </> : !error && <CircularProgress size={28} sx={{ alignSelf: "center" }} />}
          <Typography variant="body2">3. {t("mfa_setup_step3")}</Typography>
          {codeField}
          {errorBox}
          <Button type="submit" variant="contained" size="large" fullWidth disableElevation disabled={busy || !setup || code.length !== 6}>
            {t("mfa_enable_btn")}
          </Button>
          <Link component="button" type="button" variant="body2" onClick={back} sx={{ alignSelf: "flex-start" }}>{t("mfa_back_to_login")}</Link>
        </Stack>
      </Box>
    );
  }

  // 2) Har login'da: ilova kodi yoki zaxira kod
  return (
    <Box component="form" onSubmit={submit} noValidate>
      <Typography component="h1" sx={title}>{t("mfa_verify_title")}</Typography>
      <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>{t("mfa_verify_subtitle")}</Typography>
      <Stack spacing={2}>
        {codeField}
        {errorBox}
        <Button type="submit" variant="contained" size="large" fullWidth disableElevation
          disabled={busy || (backupMode ? !code.trim() : code.length !== 6)}>{t("mfa_verify_btn")}</Button>
        <Link component="button" type="button" variant="body2" sx={{ alignSelf: "flex-start" }}
          onClick={() => { setBackupMode(!backupMode); setCode(""); setError(null); }}>
          {backupMode ? t("mfa_use_app") : t("mfa_use_backup")}
        </Link>
        {backupMode && <Typography variant="body2" color="text.secondary">{t("mfa_lost_hint")}</Typography>}
        <Link component="button" type="button" variant="body2" onClick={back} sx={{ alignSelf: "flex-start" }}>{t("mfa_back_to_login")}</Link>
      </Stack>
    </Box>
  );
}
