from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Barcha sozlamalar .env yoki muhit o'zgaruvchilaridan o'qiladi."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173"

    gps_radius_default_m: int = 300
    max_upload_mb: int = 10
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    # Demo/sinov: har brauzer tabida alohida sessiya (token cookie o'rniga tab xotirasida). Prod'da o'chiq — httpOnly cookie.
    tab_sessions: bool = False

    # Tashqi GPS-monitoring tizimi uchun API kalit (X-Api-Key). Bo'sh bo'lsa integratsiya API'si o'chiq.
    integration_api_key: str = ""
    # Buyurtma varaqasi maxfiy kodining HMAC kaliti (bo'sh bo'lsa jwt_secret'dan olinadi)
    order_code_secret: str = ""

    # SMS (Eskiz.uz). Bo'sh bo'lsa SMS yuborilmaydi — faqat jurnalga yoziladi (demo)
    eskiz_email: str = ""
    eskiz_password: str = ""
    sms_sender: str = "4546"

    # SMS havolalari uchun tashqi manzil (masalan https://crm.csw.uz)
    public_base_url: str = ""
    vat_rate: float = 12.0  # QQS, %: narx QQS bilan (fakturada "shu jumladan")

    storage_backend: str = "minio"  # "memory" — MinIO'siz lokal ishlab chiqish uchun (fayllar xotirada)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio-secret"
    minio_bucket: str = "csw-files"
    minio_secure: bool = False
    minio_region: str | None = None  # UzCloud S3: "default"; MinIO uchun bo'sh

    # Faol rollar (vergul bilan, masalan "admin,manager,legal,accountant"). Bo'sh — hammasi faol. Admin har doim faol.
    active_roles: str = ""
    app_version: str = "dev"
    # Demo loginlari (APP_ENV=demo va lokal seed): JSON {"csw.admin": "parol", ...} — app/core/demo.py
    demo_credentials: str = ""  # CI rasmga commit SHA yozadi (/api/v1/health'da ko'rinadi)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def role_active(self, role: str) -> bool:
        if role == "admin" or not self.active_roles.strip():
            return True
        return role in {r.strip() for r in self.active_roles.split(",") if r.strip()}

    @property
    def active_role_list(self) -> list[str] | None:
        """None — cheklov yo'q (hamma rollar faol)."""
        if not self.active_roles.strip():
            return None
        return sorted({"admin", *(r.strip() for r in self.active_roles.split(",") if r.strip())})

    def check_production(self) -> None:
        """Prod'da xavfli standart sozlamalar bilan ishga tushmaslik; demo'da — DEMO_CREDENTIALS to'g'ri bo'lishi."""
        if self.app_env == "demo":
            from app.core.demo import DemoCredentialsError, parse
            try:
                parse(self.demo_credentials)
            except DemoCredentialsError as e:
                raise RuntimeError(f"Demo sozlamalari xato: {e}") from None
            return
        if self.app_env != "production":
            return
        problems = []
        if self.jwt_secret in ("dev-only-secret-change-me", "change-me-long-random-string") or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET standart yoki 32 belgidan qisqa")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE=true bo'lishi kerak")
        if self.tab_sessions:
            problems.append("TAB_SESSIONS prod'da o'chiq bo'lishi kerak")
        if self.storage_backend == "memory":
            problems.append("STORAGE_BACKEND=memory prod'da taqiqlangan")
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL prod'da SQLite bo'lmasligi kerak")
        from app.models.enums import Role
        unknown = {r.strip() for r in self.active_roles.split(",") if r.strip()} - {r.value for r in Role}
        if unknown:
            problems.append(f"ACTIVE_ROLES'da noma'lum rol: {', '.join(sorted(unknown))}")
        if problems:
            raise RuntimeError("Prod sozlamalari xato: " + "; ".join(problems))


def public_url() -> str:
    s = get_settings()
    return (s.public_base_url or "http://localhost:8000").rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
