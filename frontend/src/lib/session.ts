/**
 * Sessiya rejimi.
 * - Oddiy (prod): tokenlar httpOnly cookie'da — brauzerning barcha tablari bitta foydalanuvchi.
 * - Tab rejimi (demo/sinov, backend TAB_SESSIONS=true): tokenlar shu tabning sessionStorage'ida va
 *   `Authorization: Bearer` bilan yuboriladi — har tabda boshqa rolda kirish mumkin.
 */
const KEY = "csw:tab-tokens";
let tabMode = false;
let demo = false;
let activeRoles: string[] | null = null;
export interface DemoAccount { username: string; role: string }
let demoAccounts: DemoAccount[] = [];

export interface Tokens { access_token: string; refresh_token: string }

export async function detectSessionMode(): Promise<void> {
  try {
    const r = await fetch("/api/v1/auth/config", { credentials: "include" });
    if (r.ok) { const c = await r.json(); tabMode = !!c.tab_sessions; demo = !!c.demo; activeRoles = c.active_roles ?? null; demoAccounts = c.demo_accounts ?? []; }
  } catch { tabMode = false; }
}

export const isTabMode = () => tabMode;
/** Demo server: login sahifasida demo hisoblar ko'rsatiladi. */
export const isDemo = () => demo;
/** Demo hisoblar (login va rol, parolsiz) — backend DEMO_CREDENTIALS'dagi loginlar. */
export const getDemoAccounts = () => demoAccounts;
/** ACTIVE_ROLES: yangi xodim formasida faqat faol rollar. null — hammasi faol. */
export const isRoleActive = (role: string) => activeRoles === null || activeRoles.includes(role);

export function getTokens(): Tokens | null {
  if (!tabMode) return null;
  try { const raw = sessionStorage.getItem(KEY); return raw ? JSON.parse(raw) as Tokens : null; } catch { return null; }
}

export function saveTokens(data: Partial<Tokens> | null | undefined): void {
  if (!tabMode || !data?.access_token || !data.refresh_token) return;
  try { sessionStorage.setItem(KEY, JSON.stringify({ access_token: data.access_token, refresh_token: data.refresh_token })); } catch { /* yopiq xotira */ }
}

export function clearTokens(): void {
  try { sessionStorage.removeItem(KEY); } catch { /* yopiq xotira */ }
}
