import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { ApiErrorBody } from "@/types";
import { getTokens, isTabMode, saveTokens } from "@/lib/session";

export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  // Backend CSRF himoyasi shu sarlavhani talab qiladi
  headers: { "X-Requested-With": "csw" },
  timeout: 60_000,
});

// Tab rejimi: har so'rovga shu tabning tokeni
api.interceptors.request.use((cfg) => {
  if (isTabMode()) {
    cfg.headers.set("X-Session-Mode", "tab");
    const tk = getTokens();
    if (tk && !cfg.url?.startsWith("/auth/login") && !cfg.url?.startsWith("/auth/refresh")) cfg.headers.set("Authorization", `Bearer ${tk.access_token}`);
  }
  return cfg;
});

let refreshing: Promise<void> | null = null;

// Access token muddati tugasa (15 daqiqa) — bir marta refresh qilib, so'rovni qaytaramiz
api.interceptors.response.use(undefined, async (error: AxiosError<ApiErrorBody>) => {
  const cfg = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
  const isAuthCall = cfg?.url?.startsWith("/auth/");
  if (error.response?.status === 401 && cfg && !cfg._retried && !isAuthCall) {
    cfg._retried = true;
    refreshing ??= api.post("/auth/refresh", isTabMode() ? { refresh_token: getTokens()?.refresh_token } : undefined)
      .then((r) => saveTokens(r.data)).finally(() => (refreshing = null));
    try {
      await refreshing;
      return api(cfg);
    } catch {
      window.dispatchEvent(new Event("csw:logout"));
    }
  }
  return Promise.reject(error);
});

/** Backend xatosidan barqaror kodni oladi (tarjima uchun). */
export function errorCode(e: unknown): string {
  const ax = e as AxiosError<ApiErrorBody>;
  if (!ax.response) return "network";
  return ax.response.data?.error?.code ?? (ax.response.status === 422 ? "validation" : "unknown");
}

/** Xato tafsilotlari (masalan wrong_portal → {home: "legal.csw.uz"}). */
export function errorDetails(e: unknown): Record<string, unknown> | undefined {
  return (e as AxiosError<ApiErrorBody>).response?.data?.error?.details;
}

export function errorMessage(e: unknown): string | undefined {
  return (e as AxiosError<ApiErrorBody>).response?.data?.error?.message;
}
