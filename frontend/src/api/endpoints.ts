import { api } from "./client";
import { clearTokens, saveTokens, type Tokens } from "@/lib/session";
import { closeSocket } from "@/lib/socket";
import type { ContractCheck, ContractDraft, ContractItem, ExistingImportResult, TariffOverview, InvoiceItem, MonthForm, MonthFormCustomer, ProviderReq, CompanyCompare, CompanyRow, GreenItem, PaymentItem, Access, AdminUser, Appeal, OrderFormBrief, OrderPaper, ScheduleDay, ScheduleRow, Service, VehicleOption, RequestDetail, RequestItem, RequestSource, Stats, WasteType, AdminVehicle, DistrictRadius, CompleteResult, Coords, ContractType, CustomerDetail, CustomerListItem, District, DriverTask, FailReason, FileKind,
  ImportBatch, ImportResult, LocationStatus, Region, Role, SituationEvent, SituationLevel, User } from "@/types";

export const gpsApi = {
  newRequests: () => api.get<DriverTask[]>("/gps/requests").then((r) => r.data),
  vehicleOptions: (requestId: number) =>
    api.get<{ customer_has_location: boolean; items: VehicleOption[] }>(`/gps/requests/${requestId}/vehicles`).then((r) => r.data),
  assign: (requestId: number, vehicle_id: number) => api.post<DriverTask>(`/gps/requests/${requestId}/assign`, { vehicle_id }).then((r) => r.data),
  schedule: (day?: string) => api.get<ScheduleDay>("/gps/schedule", { params: { day } }).then((r) => r.data),
  saveSchedule: (rows: ScheduleRow[], day?: string) => api.put<ScheduleRow[]>("/gps/schedule", {
    rows: rows.map(({ vehicle_id, driver_id, service, mahallas }) => ({ vehicle_id, driver_id, service, mahallas })) }, { params: { day } })
    .then((r) => r.data),
  copySchedule: (from_day: string) => api.post<ScheduleRow[]>("/gps/schedule/copy", null, { params: { from_day } }).then((r) => r.data),
};

export const authApi = {
  login: (username: string, password: string) => api.post<User & Partial<Tokens>>("/auth/login", { username, password }).then((r) => {
    saveTokens(r.data);
    const { access_token: _a, refresh_token: _r, ...user } = r.data;
    return user as User;
  }),
  me: () => api.get<User>("/auth/me").then((r) => r.data),
  logout: () => api.post("/auth/logout").finally(() => { clearTokens(); closeSocket(); }),
  changePassword: (current_password: string, new_password: string) =>
    api.post<User>("/auth/change-password", { current_password, new_password }).then((r) => r.data),
};

export type UserCreate = { username: string; full_name: string; phone?: string | null; role: Role; district_id?: number | null;
  district_ids?: number[]; language?: string; password: string };
export type UserPatch = Partial<Pick<AdminUser, "full_name" | "phone" | "role" | "district_id" | "district_ids" | "language" | "is_active">>;
type Settings = { gps_radius_m: number; districts: DistrictRadius[] };

export const adminApi = {
  users: () => api.get<AdminUser[]>("/admin/users").then((r) => r.data),
  createUser: (body: UserCreate) => api.post<AdminUser>("/admin/users", body).then((r) => r.data),
  updateUser: (id: number, body: UserPatch) => api.patch<AdminUser>(`/admin/users/${id}`, body).then((r) => r.data),
  resetPassword: (id: number, password: string) => api.post<AdminUser>(`/admin/users/${id}/reset-password`, { password }).then((r) => r.data),
  regions: () => api.get<Region[]>("/admin/regions").then((r) => r.data),
  districts: () => api.get<District[]>("/admin/districts").then((r) => r.data),
  createDistrict: (name: string, region_id: number) => api.post<District>("/admin/districts", { name, region_id }).then((r) => r.data),
  updateDistrict: (id: number, body: Partial<Pick<District, "name" | "is_active">>) => api.patch<District>(`/admin/districts/${id}`, body).then((r) => r.data),
  vehicles: () => api.get<AdminVehicle[]>("/admin/vehicles").then((r) => r.data),
  createVehicle: (body: { plate: string; model?: string | null; district_id: number }) => api.post<AdminVehicle>("/admin/vehicles", body).then((r) => r.data),
  updateVehicle: (id: number, body: Partial<Omit<AdminVehicle, "id">>) => api.patch<AdminVehicle>(`/admin/vehicles/${id}`, body).then((r) => r.data),
  settings: () => api.get<Settings>("/admin/settings").then((r) => r.data),
  saveSettings: (gps_radius_m: number) => api.put<Settings>("/admin/settings", { gps_radius_m }).then((r) => r.data),
  saveDistrictRadius: (id: number, gps_radius_m: number | null) => api.put<Settings>(`/admin/districts/${id}/radius`, { gps_radius_m }).then((r) => r.data),
  setPrintMode: (id: number, manual: boolean) => api.put<Settings>(`/admin/districts/${id}/print-mode`, { manual }).then((r) => r.data),
  approveUser: (id: number) => api.post<AdminUser>(`/admin/users/${id}/approve`).then((r) => r.data),
  rejectUser: (id: number) => api.post<AdminUser>(`/admin/users/${id}/reject`).then((r) => r.data),
  permissionCatalog: () => api.get<{ modules: Record<string, string[]> }>("/admin/permissions/catalog").then((r) => r.data),
  access: (id: number) => api.get<Access>(`/admin/users/${id}/access`).then((r) => r.data),
  saveAccess: (id: number, body: { permissions: string[]; district_ids?: number[] }) =>
    api.put<Access>(`/admin/users/${id}/access`, body).then((r) => r.data),
};

export const driverApi = {
  today: () => api.get<{ day: string; vehicle: { id: number; plate: string; model: string | null } | null; service: Service | null }>(
    "/driver/today").then((r) => r.data),
  done: () => api.get<DriverTask[]>("/driver/done").then((r) => r.data),
  tasks: () => api.get<DriverTask[]>("/driver/tasks").then((r) => r.data),
  enroute: (id: number) => api.post<DriverTask>(`/driver/requests/${id}/enroute`).then((r) => r.data),
  upload: (id: number, kind: FileKind, file: Blob, coords?: Coords | null) => {
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file, `${kind}.${file.type === "image/png" ? "png" : "jpg"}`);
    if (coords) {
      fd.append("lat", String(coords.lat));
      fd.append("lng", String(coords.lng));
      if (coords.accuracy != null) fd.append("accuracy", String(coords.accuracy));
    }
    return api.post(`/driver/requests/${id}/files`, fd).then((r) => r.data);
  },
  location: (c: Coords) => api.post("/driver/location", { lat: c.lat, lng: c.lng, accuracy_m: c.accuracy }),
  complete: (id: number, body: { containers: number; volume_m3: number; note: string; lat: number; lng: number }) =>
    api.post<CompleteResult>(`/driver/requests/${id}/complete`, body).then((r) => r.data),
  fail: (id: number, reason: FailReason, note?: string) =>
    api.post<DriverTask>(`/driver/requests/${id}/fail`, { reason, note }).then((r) => r.data),
};

export type CustomerQuery = { district_id?: number; q?: string; incomplete?: boolean; location?: LocationStatus; limit?: number; offset?: number };
export type CustomerFields = { name: string; district_id: number; stir?: string | null; director?: string | null; phone?: string | null; address?: string | null; activity_type?: string | null };
export type ContractCreate = { number: string; type: ContractType; signed_on?: string | null; price?: number | null; valid_from: string; valid_to: string };

export const customersApi = {
  search: (params: CustomerQuery) => api.get<{ items: CustomerListItem[]; total: number }>("/customers", { params }).then((r) => r.data),
  get: (id: number) => api.get<CustomerDetail>(`/customers/${id}`).then((r) => r.data),
  create: (body: CustomerFields) => api.post<CustomerDetail>("/customers", body).then((r) => r.data),
  update: (id: number, body: Partial<Omit<CustomerFields, "district_id">>) => api.patch<CustomerDetail>(`/customers/${id}`, body).then((r) => r.data),
  addContact: (id: number, body: { name?: string | null; phone: string }) => api.post<CustomerDetail>(`/customers/${id}/contacts`, body).then((r) => r.data),
  addContract: (id: number, body: ContractCreate) => api.post<CustomerDetail>(`/customers/${id}/contracts`, body).then((r) => r.data),
  confirmLocation: (id: number, coords?: { lat: number; lng: number }) =>
    api.post<CustomerDetail>(`/customers/${id}/location/confirm`, coords ?? {}).then((r) => r.data),
  importFile: (file: File, dryRun: boolean) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return api.post<ImportResult>("/admin/import/customers", fd, { params: { dry_run: dryRun }, timeout: 180_000 }).then((r) => r.data);
  },
  batches: () => api.get<ImportBatch[]>("/admin/import/batches").then((r) => r.data),
};

export type SituationQuery = { level?: SituationLevel; kind?: string; district_id?: number; date_from?: string; date_to?: string;
  unread?: boolean; limit?: number; offset?: number };

export const situationApi = {
  list: (params: SituationQuery) =>
    api.get<{ items: SituationEvent[]; total: number; unread: number; last_read_id: number }>("/situation", { params }).then((r) => r.data),
  unread: () => api.get<{ unread: number }>("/situation/unread").then((r) => r.data),
  markRead: (up_to_id?: number) => api.post<{ unread: number; last_read_id: number }>("/situation/read", { up_to_id }).then((r) => r.data),
  exportFile: (params: { kind?: string; level?: string; district_id?: number; date_from?: string; date_to?: string }) =>
    api.get<Blob>("/situation/export", { params, responseType: "blob", timeout: 120_000 }).then((r) => r.data),
};

export type OrderFields = { waste_type: WasteType; volume_estimate?: number | null; preferred_time?: string | null; note?: string | null;
  caller_name?: string | null; caller_phone?: string | null; source: RequestSource };
export type AppealCreate = OrderFields & { district_id: number; org_name: string; stir?: string | null; address?: string | null; activity_type?: string | null };

export const requestsApi = {
  detail: (id: number) => api.get<RequestDetail>(`/requests/${id}`).then((r) => r.data),
  markSeen: (request_ids: number[]) => api.post("/requests/seen", { request_ids }),
  summary: (hours: number, district_id?: number) => api.get<{ hours: number; red: number; black: number; yellow: number; green: number }>(
    "/requests-summary", { params: { hours, district_id } }).then((r) => r.data),
  list: (params: { hours?: number; stage?: "red" | "black" | "yellow" | "green"; mine?: boolean; overdue?: boolean; repeat?: boolean; status?: string; district_id?: number; waste_type?: string;
    date_from?: string; date_to?: string; q?: string; limit?: number; offset?: number }) =>
    api.get<{ items: RequestItem[]; total: number }>("/requests", { params }).then((r) => r.data),
  openFor: (customer_id: number) => api.get<RequestItem[]>("/requests/open", { params: { customer_id } }).then((r) => r.data),
  create: (body: OrderFields & { customer_id: number; confirm_repeat?: boolean }) => api.post<RequestItem>("/requests", body).then((r) => r.data),
  cancel: (id: number, reason: string) => api.post<RequestItem>(`/requests/${id}/cancel`, { reason }).then((r) => r.data),
};

export const appealsApi = {
  list: (params: { status?: string; mine?: boolean }) => api.get<Appeal[]>("/appeals", { params }).then((r) => r.data),
  create: (body: AppealCreate) => api.post<Appeal>("/appeals", body).then((r) => r.data),
  newCompany: (body: { phone: string; stir: string; contact_name: string; district_id: number | null }) =>
    api.post<Appeal>("/appeals/new-company", body).then((r) => r.data),
  accept: (id: number, body: { customer: CustomerFields; contract?: ContractCreate | null }) =>
    api.post<Appeal>(`/appeals/${id}/accept`, body).then((r) => r.data),
  reject: (id: number, reason: string) => api.post<Appeal>(`/appeals/${id}/reject`, { reason }).then((r) => r.data),
};

export type StatPeriod = "today" | "month" | "last10" | "last5";
export type StatMetric = "received" | "repeat" | "pending" | "overdue" | "done" | "not_done";
export interface StatDetail {
  period: StatPeriod; metric: StatMetric; since: string; value: number; granularity: "hour" | "day";
  series: { label: string; date?: string; value: number }[];
  composition: { key: string; value: number }[];
  histogram: { bucket: string; value: number }[];
  districts: { district_id: number; name: string; value: number }[];
}

export const statsApi = {
  summary: (period: StatPeriod) => api.get<Stats>("/stats/summary", { params: { period } }).then((r) => r.data),
  detail: (period: StatPeriod, metric: StatMetric) => api.get<StatDetail>("/stats/detail", { params: { period, metric } }).then((r) => r.data),
  /** Fayl sifatida yuklab olish (tab sessiyasida ham token bilan) */
  export: async (period: StatPeriod, metric: StatMetric, format: "xlsx" | "pdf") => {
    const r = await api.get<Blob>("/stats/export", { params: { period, metric, format }, responseType: "blob", timeout: 120_000 });
    const name = /filename="([^"]+)"/.exec(r.headers["content-disposition"] ?? "")?.[1] ?? `statistika.${format}`;
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  },
};

export const ordersApi = {
  paper: (id: number) => api.get<OrderPaper>(`/order-forms/${id}`).then((r) => r.data),
  /** PDF faqat chop etish uchun (maxfiy kod shu faylda) — ekranda ko'rsatilmaydi */
  print: (id: number) => api.post<Blob>(`/order-forms/${id}/print`, null, { responseType: "blob", timeout: 60_000 }).then((r) => r.data),
  allowReprint: (id: number) => api.post<OrderFormBrief>(`/order-forms/${id}/allow-reprint`).then((r) => r.data),
  confirmPrint: (id: number) => api.post<{ request_id: number; status: string; form: OrderFormBrief }>(`/order-forms/${id}/confirm-print`).then((r) => r.data),
  unlock: (id: number) => api.post<OrderFormBrief>(`/order-forms/${id}/unlock`).then((r) => r.data),
  uploadScan: (id: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return api.post<OrderFormBrief>(`/order-forms/${id}/scan`, fd, { timeout: 60_000 }).then((r) => r.data);
  },
  scan: (id: number) => api.get<Blob>(`/order-forms/${id}/scan`, { responseType: "blob" }).then((r) => r.data),
  verify: (id: number, code: string) => api.post<OrderPaper>(`/order-forms/${id}/verify`, { code }).then((r) => r.data),
  close: (id: number, volume_m3: number, waste_kind: "solid" | "liquid") =>
    api.post<RequestItem>(`/order-forms/${id}/close`, { volume_m3, waste_kind }).then((r) => r.data),
};

export type NewPeriod = "d7" | "d15" | "m1" | "m6" | "y1";
export const accountingApi = {
  companies: (q?: string, district_id?: number) => api.get<{ total_contracted: number; total: number; items: CompanyRow[];
    sum: { debit: number; credit: number; volume_m3: number } }>("/accounting/companies", { params: { q, district_id } }).then((r) => r.data),
  newContracts: (district_id?: number) => api.get<{ today: string; periods: { key: NewPeriod; days: number; since: string; count: number }[];
    districts: ({ district_id: number; name: string } & Record<NewPeriod, number>)[] }>("/accounting/new-contracts", { params: { district_id } })
    .then((r) => r.data),
  compare: (id: number, a: [string, string], b: [string, string]) => api.get<CompanyCompare>(`/accounting/companies/${id}/compare`,
    { params: { a_from: a[0], a_to: a[1], b_from: b[0], b_to: b[1] } }).then((r) => r.data),
  green: (id: number) => api.get<{ customer: CompanyCompare["customer"]; items: GreenItem[]; total_m3: number; count: number }>(
    `/accounting/companies/${id}/green`).then((r) => r.data),
  payments: (params: { q?: string; date_from?: string; date_to?: string; customer_id?: number; limit?: number; offset?: number }) =>
    api.get<{ items: PaymentItem[]; total: number; sum: number }>("/accounting/payments", { params }).then((r) => r.data),
  addPayment: (body: { customer_id: number; paid_on: string; amount: number; doc_no?: string | null; note?: string | null }) =>
    api.post<PaymentItem>("/accounting/payments", body).then((r) => r.data),
  cancelPayment: (id: number, reason: string) => api.post<PaymentItem>(`/accounting/payments/${id}/cancel`, { reason }).then((r) => r.data),
  importPayments: (file: File, dry_run: boolean) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return api.post<{ dry_run: boolean; ok: number; total: number; errors: { line: number; error: string; value: string }[];
      rows: { line: number; name: string; code: string; paid_on: string; amount: number; doc_no: string | null }[] }>(
      "/accounting/payments/import", fd, { params: { dry_run }, timeout: 120_000 }).then((r) => r.data);
  },
  orderForms: (month: string, district_id?: number, customer_id?: number) => api.get<{ month: string; items: MonthForm[];
    customers: MonthFormCustomer[]; total: number; count: number; pending: number }>("/accounting/order-forms", { params: { month, district_id, customer_id } })
    .then((r) => r.data),
  invoices: (month: string, district_id?: number) => api.get<{ month: string; items: InvoiceItem[]; total: number; drafts: number; sent: number }>(
    "/accounting/invoices", { params: { month, district_id } }).then((r) => r.data),
  generateInvoices: (month: string) => api.post<{ created: number; updated: number; skipped_sent: number; pending_forms: number }>("/accounting/invoices/generate", null,
    { params: { month }, timeout: 120_000 }).then((r) => r.data),
  sendInvoices: (month: string) => api.post<{ sent: number; no_phone: number; total: number }>("/accounting/invoices/send", null,
    { params: { month }, timeout: 120_000 }).then((r) => r.data),
  invoicePdf: (id: number) => api.get<Blob>(`/accounting/invoices/${id}/pdf`, { responseType: "blob", timeout: 60_000 }).then((r) => r.data),
};

export const providersApi = {
  list: () => api.get<ProviderReq[]>("/admin/providers").then((r) => r.data),
  save: (id: number, body: Partial<ProviderReq>) => api.put<ProviderReq>(`/admin/providers/${id}`, body).then((r) => r.data),
};

export const contractsApi = {
  check: (body: ContractDraft, id?: number) => api.post<ContractCheck>(id ? `/contracts/${id}/check` : "/contracts/check", body).then((r) => r.data),
  create: (body: ContractDraft) => api.post<ContractItem>("/contracts", body).then((r) => r.data),
  start: (customer_id: number) => api.post<ContractItem>("/contracts/start", { customer_id }).then((r) => r.data),
  saveDraft: (id: number, body: ContractDraft) => api.put<ContractItem>(`/contracts/${id}/draft`, body).then((r) => r.data),
  createExisting: (body: ContractDraft) => api.post<ContractItem>("/contracts/existing", body).then((r) => r.data),
  existingTemplate: () => api.get<Blob>("/contracts/existing/template", { responseType: "blob" }).then((r) => r.data),
  importExisting: (file: File, dry_run: boolean) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return api.post<ExistingImportResult>("/contracts/existing/import", fd, { params: { dry_run }, timeout: 180_000 }).then((r) => r.data);
  },
  uploadScan: (id: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return api.post<ContractItem>(`/contracts/${id}/scan-upload`, fd, { timeout: 60_000 }).then((r) => r.data);
  },
  update: (id: number, body: ContractDraft) => api.put<ContractItem>(`/contracts/${id}`, body).then((r) => r.data),
  remove: (id: number, reason: string) => api.post(`/contracts/${id}/delete`, { reason }),
  get: (id: number) => api.get<ContractItem>(`/contracts/${id}`).then((r) => r.data),
  list: (params: { status?: string; q?: string; district_id?: number; limit?: number }) =>
    api.get<{ items: ContractItem[]; total: number }>("/contracts", { params }).then((r) => r.data),
  document: (id: number, format: "pdf" | "docx") =>
    api.get<Blob>(`/contracts/${id}/document`, { params: { format }, responseType: "blob", timeout: 60_000 }).then((r) => r.data),
  scan: (id: number) => api.get<Blob>(`/contracts/${id}/scan`, { responseType: "blob" }).then((r) => r.data),
  sign: (id: number, body: { signed_on: string; sign_method: string; platform?: string; platform_id?: string; file?: File | null }) => {
    const fd = new FormData();
    fd.append("signed_on", body.signed_on);
    fd.append("sign_method", body.sign_method);
    if (body.platform) fd.append("platform", body.platform);
    if (body.platform_id) fd.append("platform_id", body.platform_id);
    if (body.file) fd.append("file", body.file, body.file.name);
    return api.post<ContractItem>(`/contracts/${id}/sign`, fd, { timeout: 60_000 }).then((r) => r.data);
  },
  approve: (id: number) => api.post<ContractItem>(`/contracts/${id}/approve`).then((r) => r.data),
  returnBack: (id: number, comment: string) => api.post<ContractItem>(`/contracts/${id}/return`, { comment }).then((r) => r.data),
};

export const tariffsApi = {
  overview: () => api.get<TariffOverview>("/tariffs").then((r) => r.data),
  price: (district_id: number, day?: string) => api.get<{ price: number | null }>("/tariffs/price", { params: { district_id, day } }).then((r) => r.data),
  set: (body: { region_id?: number; district_id?: number; price: number; valid_from: string; note?: string | null }) =>
    api.post("/tariffs", body).then((r) => r.data),
  remove: (id: number) => api.delete(`/tariffs/${id}`),
  lock: (body: { region_id?: number; district_id?: number; locked: boolean }) => api.put("/tariffs/lock", body),
};
