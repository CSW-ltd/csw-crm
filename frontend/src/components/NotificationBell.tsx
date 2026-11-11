/** Shaxsiy bildirishnomalar (masalan, GPS joylashuvni o'zgartirdi — shartnomani kiritgan legal'ga): qo'ng'iroqcha, o'qilmaganlar soni,
 * ro'yxat; Socket.IO "notification:new" — jonli (toast). */
import { useCallback, useEffect, useState } from "react";
import { Badge, Box, Button, Divider, IconButton, Popover, Stack, Typography } from "@mui/material";
import MarkEmailUnreadIcon from "@mui/icons-material/MarkEmailUnread";
import { notificationsApi } from "@/api/endpoints";
import { useI18n } from "@/i18n/I18nContext";
import { MESSAGES, type MessageKey } from "@/i18n/messages";
import { toast } from "@/lib/alerts";
import { formatDateTime } from "@/lib/format";
import { getSocket } from "@/lib/socket";
import type { NotificationItem } from "@/types";

export function NotificationBell() {
  const { t } = useI18n();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const text = useCallback((n: NotificationItem) => {
    const key = `n_${n.kind}` as MessageKey;
    if (!(key in MESSAGES) || !n.params) return n.message;
    const p: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(n.params)) if (v !== null && v !== undefined) p[k] = v as string | number;
    return t(key, p);
  }, [t]);
  const load = useCallback(async () => { const r = await notificationsApi.mine(); setItems(r.items); setUnread(r.unread); }, []);
  useEffect(() => {
    load().catch(() => undefined);
    const s = getSocket();
    const on = (n: NotificationItem) => { setItems((xs) => [n, ...xs].slice(0, 50)); setUnread((u) => u + 1); toast(text(n), "info"); };
    s.on("notification:new", on);
    return () => { s.off("notification:new", on); };
  }, [load, text]);
  const readAll = async () => { await notificationsApi.read(); setUnread(0); setItems((xs) => xs.map((x) => ({ ...x, read: true }))); };
  return (
    <>
      <IconButton aria-label={t("notif_title")} onClick={(e) => setAnchor(e.currentTarget)} id="notif-bell">
        <Badge color="error" badgeContent={unread}><MarkEmailUnreadIcon /></Badge>
      </IconButton>
      <Popover open={!!anchor} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }} slotProps={{ paper: { sx: { width: { xs: "92vw", sm: 420 }, maxHeight: 480 } } }}>
        <Stack direction="row" alignItems="center" sx={{ px: 2, py: 1 }}>
          <Typography fontWeight={700} sx={{ flex: 1 }}>{t("notif_title")}</Typography>
          {unread > 0 && <Button size="small" onClick={readAll} id="notif-read-all">{t("notif_read_all")}</Button>}
        </Stack>
        <Divider />
        {!items.length && <Typography color="text.secondary" sx={{ p: 2 }}>{t("notif_empty")}</Typography>}
        {items.map((n) => (
          <Box key={n.id} data-notif={n.kind} sx={{ px: 2, py: 1.25, borderBottom: 1, borderColor: "divider", bgcolor: n.read ? undefined : "action.hover" }}>
            <Typography variant="body2" fontWeight={n.read ? 400 : 600}>{text(n)}</Typography>
            <Typography variant="caption" color="text.secondary">{formatDateTime(new Date(n.created_at + "Z"))}</Typography>
          </Box>
        ))}
      </Popover>
    </>
  );
}
