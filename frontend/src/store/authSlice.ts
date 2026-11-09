import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { authApi } from "@/api/endpoints";
import { errorCode, errorDetails } from "@/api/client";
import type { User } from "@/types";

/** errorHome — wrong_portal bo'lsa foydalanuvchining o'z portali (masalan legal.csw.uz). */
interface AuthState { user: User | null; status: "unknown" | "loading" | "ready"; error: string | null; errorHome: string | null }
const initialState: AuthState = { user: null, status: "unknown", error: null, errorHome: null };

export const loadMe = createAsyncThunk("auth/me", async () => {
  try { return await authApi.me(); } catch { return null; }
});

export const login = createAsyncThunk<User, { username: string; password: string }, { rejectValue: { code: string; home: string | null } }>(
  "auth/login",
  async ({ username, password }, { rejectWithValue }) => {
    try { return await authApi.login(username, password); } catch (e) {
      const home = errorDetails(e)?.home;
      return rejectWithValue({ code: errorCode(e), home: typeof home === "string" ? home : null });
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
  },
  extraReducers: (b) => {
    b.addCase(loadMe.pending, (s) => { s.status = "loading"; })
      .addCase(loadMe.fulfilled, (s, a) => { s.user = a.payload; s.status = "ready"; })
      .addCase(login.pending, (s) => { s.error = null; s.errorHome = null; })
      .addCase(login.fulfilled, (s, a) => { s.user = a.payload; s.status = "ready"; })
      .addCase(login.rejected, (s, a) => { s.error = a.payload?.code ?? "unknown"; s.errorHome = a.payload?.home ?? null; })
      .addCase(logout.fulfilled, (s) => { s.user = null; });
  },
});

export const { sessionExpired, setUser } = slice.actions;
export default slice.reducer;
