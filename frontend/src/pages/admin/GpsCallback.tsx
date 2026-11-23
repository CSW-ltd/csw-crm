import { useEffect, useRef, useState } from "react";
import { Alert, CircularProgress, Stack, Typography } from "@mui/material";
import { Navigate, useParams } from "react-router-dom";
import { dispatchApi } from "@/api/endpoints";
import { errorCode, errorMessage } from "@/api/client";
import { useI18n } from "@/i18n/I18nContext";
import { toast } from "@/lib/alerts";

/** SmartGPS login.html shu sahifaga `?access_token=…` bilan qaytaradi. Token darhol manzil satridan o'chiriladi (tarixda qolmasin),
 *  shifrlab saqlash uchun serverga yuboriladi, keyin «Geozonalar» tabiga qaytiladi. */
export function GpsCallback() {
  const { t, tErr } = useI18n();
  const { id, slot } = useParams();
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const q = new URLSearchParams(window.location.search);
    const token = q.get("access_token");
    const svcErr = q.get("svc_error");
    window.history.replaceState(null, "", window.location.pathname);
    if (!token || (svcErr && svcErr !== "0")) { setErr(t("gpsc_cb_failed")); return; }
    dispatchApi.setToken(Number(id), token, slot === "backup" ? "backup" : "main")
      .then(() => { toast(t("gpsc_token_saved"), "success"); setDone(true); })
      .catch((e) => setErr(tErr(errorCode(e), errorMessage(e))));
  }, [id, slot, t, tErr]);
  if (done) return <Navigate to="/admin#geozones" replace />;
  return (
    <Stack spacing={2} alignItems="center" sx={{ mt: 6 }}>
      {err ? <Alert severity="error" action={<a href="/admin#geozones">{t("back")}</a>}>{err}</Alert>
        : <><CircularProgress /><Typography>{t("gpsc_cb_saving")}</Typography></>}
    </Stack>
  );
}
