export type Role = "admin" | "manager" | "operator" | "gps" | "legal" | "driver" | "accountant";
export type ShiftStatus = "opened" | "active" | "closed";
export type RequestStatus = "new" | "printing" | "assigned" | "enroute" | "onsite" | "done" | "suspect" | "failed" | "cancelled";
export type FileKind = "before" | "after" | "face" | "sign";
export type FailReason = "no_waste" | "no_recipient" | "no_access";

export interface User {
  id: number;
  username: string;
  full_name: string;
  phone: string | null;
  role: Role;
  district_id: number | null;
  language: string;
  must_change_password: boolean;
  /** Ruxsat kodlari ("customers.edit" ...); admin — hammasi */
  permissions?: string[];
  /** Ishlash doirasi (tumanlar) */
  district_ids?: number[];
}

export interface AdminUser extends User {
  is_active: boolean;
  locked_until: string | null;
  created_at: string;
  district_ids: number[];
  permissions: string[];
  approval_status: "approved" | "pending" | "rejected";
  created_by_id: number | null;
}

export interface Access {
  user_id: number;
  role: Role;
  permissions: string[];
  district_ids: number[];
  multi_district: boolean;
  grantable: string[];
  assignable_district_ids: number[] | null;
}

export interface DistrictRadius {
  print_manual_confirm?: boolean; id: number; name: string; gps_radius_m: number | null; effective_m: number }

export interface Region { id: number; name: string }
export interface District { id: number; name: string; region_id: number; is_active: boolean; gps_radius_m?: number | null }
export interface AdminVehicle { id: number; plate: string; model: string | null; district_id: number; is_active: boolean }

export interface Vehicle {
  id: number;
  plate: string;
  model: string | null;
  district_id: number;
}

export interface Shift {
  id: number;
  status: ShiftStatus;
  driver_id: number;
  district_id: number;
  vehicle: Vehicle;
  started_at: string | null;
  ended_at: string | null;
  odometer_start: number | null;
  odometer_end: number | null;
  fuel_start: string | null;
  fuel_end: string | null;
  distance_km: number | null;
  fuel_used: string | null;
}

export interface GpsDriver {
  id: number;
  full_name: string;
  phone: string | null;
  shift: Shift | null;
}

export type LocationStatus = "none" | "pending" | "confirmed";

export interface Customer {
  id: number;
  fixed_no: string;
  /** Korxona maxsus raqami (3 harf + 2 raqam, masalan KTR47) — STIR o'rniga */
  code: string | null;
  stir: string | null;
  name: string;
  director: string | null;
  phone: string | null;
  address: string | null;
  district_id: number;
  lat: number | null;
  lng: number | null;
  location_status: LocationStatus;
  /** "stir" | "contract" — bo'lsa haydovchi biriktirilmaydi */
  missing_fields: string[];
  /** oxirgi 30 kunda imzolangan shartnoma — GPS kartasida «Yangi shartnoma» */
  new_contract?: boolean;
}

export interface CustomerListItem extends Customer {
  activity_type: string | null;
  source: "excel" | "manual" | string;
  contacts_count: number;
}

export interface Contact { id: number; name: string | null; phone: string }

export type ContractType = "per_trip" | "by_volume" | "monthly" | "one_off";

export interface ContractFull {
  id: number;
  number: string;
  signed_on: string | null;
  type: ContractType;
  price: string | null;
  valid_from: string;
  valid_to: string;
  is_active: boolean;
  status?: ContractStatus;
  platform_id?: string | null;
  display_number?: string | null;
  annual_volume?: string | null;
}

export interface CustomerDetail extends CustomerListItem {
  legal_address?: string | null; bank?: string | null; mfo?: string | null; account?: string | null; oked?: string | null; cadastre?: string | null;
  contacts: Contact[];
  contracts: ContractFull[];
  created_at: string;
}

export interface ImportResult {
  sheet: string;
  file_kind: string;
  rows_total: number;
  rows_ok: number;
  rows_skipped: number;
  septic_rows: number;
  customers_new: number;
  customers_existing: number;
  contacts_added: number;
  by_district: Record<string, number>;
  errors: { row: number; message: string }[];
  batch_id: number | null;
  dry_run: boolean;
}

export interface ImportBatch {
  id: number;
  file_name: string;
  uploaded_by_id: number;
  rows_total: number;
  customers_created: number;
  customers_merged: number;
  rows_skipped: number;
  created_at: string;
}

export interface Contract {
  id: number;
  number: string;
  signed_on: string | null;
  type: string;
}

export interface DriverTask {
  id: number;
  number: string | null;
  status: RequestStatus;
  waste_type: string;
  volume_estimate: string | null;
  preferred_time: string | null;
  note: string | null;
  naryad_no: string | null;
  district_id: number;
  driver_id: number | null;
  created_at: string;
  assigned_at: string | null;
  customer: Customer;
  contract: Contract | null;
  files: FileKind[];
  source?: RequestSource;
  due_at?: string | null;
  overdue?: boolean;
  is_repeat?: boolean;
  seen?: boolean | null;
  stage?: Stage;
  vehicle?: Vehicle | null;
  driver_name?: string | null;
  finished_at?: string | null;
  order_form?: OrderFormBrief | null;
}

/** Uch bosqich: qizil — mashina biriktirilmagan, sariq — chiqindi olinishi kutilmoqda, yashil — bajarilgan */
export type Stage = "red" | "black" | "yellow" | "green" | "cancelled";
export interface OrderFormBrief {
  id: number;
  number: string;
  print_confirmed?: boolean;
  print_confirm_via?: string | null;
  printed: boolean;
  print_count: number;
  printed_at: string | null;
  reprint_allowed: boolean;
  locked: boolean;
  attempts_left: number;
  has_scan: boolean;
  verified: boolean;
  closed_at: string | null;
  closed_via: "form" | "act" | null;
  volume_m3: number | null;
  waste_kind: "solid" | "liquid" | null;
}
/** Varaqaning qog'oz ko'rinishi (maxfiy kodsiz) */
export interface OrderPaper {
  form: OrderFormBrief;
  request_number: string | null;
  provider: string;
  customer: { name: string; code: string | null; address: string | null };
  vehicle: { plate: string; model: string | null } | null;
  driver_name: string | null;
  assigned_at: string | null;
  waste_type: string;
  /** printerdan chiqqani hali tasdiqlanmagan (karta qizil) */
  awaiting_print?: boolean;
  /** qayta biriktirilgan — yangi mashina bilan qayta chop etish kerak */
  needs_reprint?: boolean;
  /** tumanda agentsiz rejim: GPS «Varaqa chiqdi»ni o'zi bosadi */
  manual_confirm?: boolean;
}
export type Service = "legal" | "individual";
export interface ScheduleRow { id?: number; vehicle_id: number; plate?: string; model?: string | null; driver_id: number | null;
  driver_name?: string | null; service: Service; mahallas: string | null }
export interface ScheduleDay { day: string; district_id: number; rows: ScheduleRow[];
  vehicles: { id: number; plate: string; model: string | null }[]; drivers: { id: number; full_name: string; phone: string | null }[] }
export interface VehicleOption { vehicle_id: number; plate: string; model: string | null; service: Service | null; driver_id: number | null;
  driver_name: string | null; distance_m: number | null; position_at: string | null; position_source: string | null; available: boolean }

export type RequestSource = "phone" | "telegram" | "excel" | "walk_in";
export type WasteType = "household" | "construction" | "bulky" | "green" | "septic";

export interface RequestItem extends Omit<DriverTask, "files"> {
  caller_name: string | null;
  caller_phone: string | null;
  repeat_of_id: number | null;
  created_by_id: number | null;
  finished_at: string | null;
  cancel_reason: string | null;
}

export interface RequestDetail extends RequestItem {
  driver_name: string | null;
  created_by_name: string | null;
  events: { status: RequestStatus; note: string | null; actor_name: string | null; created_at: string }[];
}

export interface Appeal {
  id: number;
  number: string | null;
  status: "new" | "accepted" | "rejected";
  district_id: number;
  org_name: string;
  stir: string | null;
  address: string | null;
  activity_type: string | null;
  caller_name: string | null;
  caller_phone: string | null;
  source: RequestSource;
  waste_type: WasteType;
  volume_estimate: string | null;
  preferred_time: string | null;
  note: string | null;
  created_by_id: number | null;
  reviewed_at: string | null;
  reject_reason: string | null;
  customer_id: number | null;
  request_id: number | null;
  created_at: string;
}

export interface StatMetrics {
  received: number; repeat: number; pending: number; overdue: number; done: number; not_done: number;
  done_share: number; not_done_share: number;
}
export interface Stats { period: string; since: string; total: StatMetrics; districts: (StatMetrics & { district_id: number; name: string })[] }

export interface CompleteResult {
  request: DriverTask;
  act: { containers: number; volume_m3: string; distance_m: number | null; radius_m: number; in_radius: boolean | null; vehicle_plate: string; completed_at: string };
}

export interface ApiErrorBody {
  error?: { code: string; message: string };
  detail?: unknown;
}

export interface Coords {
  lat: number;
  lng: number;
  accuracy?: number;
}

export type SituationLevel = "info" | "warning" | "error" | "activity";

export interface SituationEvent {
  id: number;
  level: SituationLevel;
  kind: string;
  message: string;
  params: Record<string, unknown>;
  district_id: number | null;
  actor_id: number | null;
  actor_name?: string | null;
  ref_type: string | null;
  ref_id: number | null;
  created_at: string;
  resolved?: boolean;
}


export interface CompanyRow { customer_id: number; name: string; code: string | null; district_id: number; debit: number; credit: number;
  balance: number; volume_m3: number; green_count: number }
export interface CompanyPeriod { from: string; to: string; opening: number; charged: number; paid: number; closing: number; debit: number; credit: number }
export interface CompanyCompare { customer: { id: number; name: string; code: string | null; stir: string | null }; periods: CompanyPeriod[];
  months: { month: string; charged: number; paid: number; closing: number }[]; now: CompanyRow }
export interface GreenItem { id: number; number: string | null; day: string; volume_m3: number; waste_type: string; plate: string | null;
  driver_name: string | null; closed_via: "form" | "act" | null; status: string; contract: string | null; amount: number }
export interface PaymentItem { id: number; customer_id: number; customer_name: string | null; code: string | null; paid_on: string; amount: number;
  doc_no: string | null; note: string | null; source: "manual" | "import"; created_at: string; cancelled: boolean; cancel_reason: string | null }

/** Buxgalteriya: oy ichida yashil bo'lgan buyurtma varaqasi (summa — amaldagi shartnoma bo'yicha) */
export interface MonthForm { request_id: number; number: string; day: string; customer_id: number; customer_name: string; code: string | null;
  district_id: number; form_number: string | null; volume_m3: number; waste_kind: string | null; plate: string | null; closed_via: string | null;
  contract: string | null; contract_type: ContractType | null; price: number | null; amount: number; pending?: boolean;
  price_source?: "tariff" | "contract" | null }
export interface MonthFormCustomer { customer_id: number; name: string; code: string | null; district_id: number; forms: number; total: number;
  pending?: number; usage?: { contract: string; annual: number; used: number; pct: number; level: "ok" | "warn" | "over" } | null }
export interface InvoiceItem { id: number; number: string; customer_id: number; customer_name: string | null; code: string | null; district_id: number | null;
  period: string; status: "draft" | "sent"; total: number; vat: number; sent_at: string | null; sms_phone: string | null; lines_count: number; forms_count: number }
export interface ProviderReq { id: number; name: string; code: string; region_id: number; full_name: string | null; inn: string | null; address: string | null;
  bank: string | null; mfo: string | null; account: string | null; director: string | null; chief_accountant: string | null;
  phone?: string | null; oked?: string | null }

/** «Yangi shartnoma» jarayoni */
export type ContractStatus = "draft" | "signed" | "returned" | "approved";
export interface Requisites { name: string; stir: string | null; director: string | null; phone: string | null; legal_address: string | null;
  address: string | null; bank: string | null; mfo: string | null; account: string | null; oked: string | null; cadastre: string | null;
  is_rented?: boolean; lat?: number | null; lng?: number | null }
export interface ContractDraft { customer_id: number; requisites: Requisites; type: ContractType; price: number | null; annual_volume: number | null;
  annual_trips: number | null; valid_from: string; valid_to: string; place: string; sign_method: "electronic" | "paper";
  existing?: { number: string; signed_on: string | null; platform?: string | null; platform_id?: string | null } | null; price_reason?: string | null }
export interface ContractCheck { ok: boolean; errors: { field: string; code: string }[];
  totals: { qty: number; unit: string; net: number; vat: number; total: number; words: string; price?: number | null; tariff?: number | null } }
export interface ContractEventItem { action: string; comment: string | null; at: string; actor: string | null }
export interface ContractItem { id: number; number: string | null; platform: string | null; platform_id: string | null; display_number: string;
  status: ContractStatus; type: ContractType; price: number | null; annual_volume: number | null; annual_trips: number | null;
  valid_from: string; valid_to: string; signed_on: string | null; place: string | null; sign_method: "electronic" | "paper" | null;
  has_scan: boolean; return_comment: string | null; signed_at: string | null; approved_at: string | null; created_at: string;
  total: number; vat: number; is_active: boolean; used_m3?: number; usage_pct?: number; usage_level?: "ok" | "warn" | "over";
  customer: Requisites & { id: number; code: string | null; district_id: number; location_status?: LocationStatus } | null; events?: ContractEventItem[];
  draft?: Partial<ContractDraft> & { requisites?: Requisites } | null; source?: "flow" | "manual" | "import"; awaiting_scan?: boolean; submitted_by?: string | null; tariff_price?: number | null; price_reason?: string | null }
export interface ExistingContract { customer_id: number; number: string; platform?: string | null; platform_id?: string | null; type: ContractType;
  price?: number | null; annual_volume?: number | null; signed_on: string; valid_from: string; valid_to: string; sign_method: "electronic" | "paper" }
export interface ExistingImportResult { dry_run: boolean; ok: number; total: number; created: number; errors: { line: number; error: string; value: string }[];
  rows: { line: number; district: string; name: string; stir: string | null; number: string; type: ContractType; valid_from: string; valid_to: string;
    existing_customer: number | null }[] }
export interface TariffHist { id: number; price: number; valid_from: string; note: string | null; created_at: string; by: string | null }
export interface TariffDistrict { district_id: number; name: string; locked: boolean; own_price: number | null; price: number | null;
  upcoming: { price: number; valid_from: string } | null; can_edit: boolean; history: TariffHist[] }
export interface TariffRegion { region_id: number; name: string; locked: boolean; price: number | null; upcoming: { price: number; valid_from: string } | null;
  can_edit: boolean; history: TariffHist[]; districts: TariffDistrict[] }
export interface TariffOverview { today: string; regions: TariffRegion[] }
