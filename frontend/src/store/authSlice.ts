import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { authApi } from "@/api/endpoints";
import { errorCode, errorDetails } from "@/api/client";
import type { User } from "@/types";

/** Admin 2FA: parol to'g'ri, endi kod kerak (setup — birinchi marta QR, verify — har login'da). */
export interface MfaChallenge { mode: "setup" | "verify"; token: string }
/** errorHome — wrong_portal bo'lsa foydalanuvchining o'z portali (masalan legal.csw.uz). */
interface AuthState { user: User | null; status: "unknown" | "loading" | "ready"; error: string | null; errorHome: string | null; mfa: MfaChallenge | null }
const initialState: AuthState = { user: null, status: "unknown", error: null, errorHome: null, mfa: null };

export const loadMe = createAsyncThunk("auth/me", async () => {
  try { return await authApi.me(); } catch { return null; }
});

type LoginReject = { code: string; home: string | null; mfa: MfaChallenge | null };
export const login = createAsyncThunk<User, { username: string; password: string }, { rejectValue: LoginReject }>(
  "auth/login",
  async ({ username, password }, { rejectWithValue }) => {
    try { return await authApi.login(username, password); } catch (e) {
      const d = errorDetails(e);
      const mfa = errorCode(e) === "mfa_required" && typeof d?.mfa_token === "string"
        ? { mode: d.mode === "setup" ? "setup" as const : "verify" as const, token: d.mfa_token } : null;
      return rejectWithValue({ code: errorCode(e), home: typeof d?.home === "string" ? d.home : null, mfa });
    }
  },
);

export const logout = createAsyncThunk("auth/logout", async () => {
  try { await authApi.logout(); } catch { /* sessiya baribir tozalanadi */ }
});

const slice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    sessionExpired: (s) => { s.user = null; s.status = "ready"; },
    setUser: (s, a: { payload: User }) => { s.user = a.payload; },
    /** 2FA tugadi (sessiya ochildi) yoki bekor qilindi */
    mfaDone: (s, a: { payload: User | null }) => { s.mfa = null; s.error = null; if (a.payload) { s.user = a.payload; s.status = "ready"; } },
  },
  extraReducers: (b) => {
    b.addCase(loadMe.pending, (s) => { s.status = "loading"; })
      .addCase(loadMe.fulfilled, (s, a) => { s.user = a.payload; s.status = "ready"; })
      .addCase(login.pending, (s) => { s.error = null; s.errorHome = null; s.mfa = null; })
      .addCase(login.fulfilled, (s, a) => { s.user = a.payload; s.status = "ready"; })
      .addCase(login.rejected, (s, a) => {
        s.mfa = a.payload?.mfa ?? null;
        s.error = s.mfa ? null : a.payload?.code ?? "unknown";
        s.errorHome = a.payload?.home ?? null;
      })
      .addCase(logout.fulfilled, (s) => { s.user = null; });
  },
});

export const { sessionExpired, setUser, mfaDone } = slice.actions;
export default slice.reducer;
