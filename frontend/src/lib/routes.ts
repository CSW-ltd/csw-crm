import type { User } from "@/types";

/** Har bir rolning bosh sahifasi. Hali ekrani yo'q rollar "/" da qoladi. */
export function homePath(user: User): string {
  if (user.must_change_password) return "/change-password";
  switch (user.role) {
    case "driver": return "/driver";
    case "gps": return "/gps";
    case "operator": return "/operator";
    case "admin":
    case "manager":
    case "legal":
    case "accountant": return "/admin";
    default: return "/";
  }
}

/** Kirgandan keyin: oxirgi ochilgan sahifa shu rolga tegishli bo'lsa — o'sha, aks holda bosh sahifa. */
export function afterLoginPath(user: User, last: string | null): string {
  const home = homePath(user);
  if (!last || home === "/" || home === "/change-password") return home;
  return last === home || last.startsWith(`${home}#`) || last.startsWith(`${home}/`) || last.startsWith(`${home}?`) ? last : home;
}
