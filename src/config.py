from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_env_wrappers(value: object) -> object:
    if not isinstance(value, str):
        return value
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1].strip()
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tiflux_api_token: str = ""
    vhsys_access_token: str = ""
    vhsys_secret_access_token: str = ""
    brasilapi_base_url: str = "https://brasilapi.com.br/api/cnpj/v1"
    tiflux_base_url: str = "https://api.tiflux.com/api/v2"
    # Cliente existente com mesas/grupos corretos; 0 = primeiro da listagem
    tiflux_reference_client_id: int = 31116
    tiflux_desk_ids: str = ""
    tiflux_technical_group_ids: str = ""
    vhsys_base_url: str = "https://api.vhsys.com/v2"
    require_active_cnpj: bool = True
    user_agent: str = "AVS-Management/1.4"
    tiflux_default_desk_names: str = "Comercial,Serviços Avulsos,Vendas"
    auth_enabled: bool = False
    auth_provider: str = "local"
    session_secret: str = "change-me-in-production"
    app_base_url: str = "http://127.0.0.1:8000"
    # vazio = inferir pelo APP_BASE_URL | development | production
    app_env: str = ""
    auth_db_path: str = "data/auth.db"
    session_idle_hours: int = 8
    remember_me_days: int = 30
    password_reset_token_hours: int = 1
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_redirect_uri: str = "http://127.0.0.1:8000/auth/callback"
    allowed_user_emails: str = ""
    trusted_proxy_ips: str = "127.0.0.1"
    tiflux_min_request_interval_ms: int = 400
    tiflux_dormant_scan_max: int = 0
    tiflux_dormant_batch_pause_every: int = 20
    tiflux_dormant_batch_pause_ms: int = 2000

    @field_validator(
        "tiflux_api_token",
        "vhsys_access_token",
        "vhsys_secret_access_token",
        "azure_client_secret",
        "session_secret",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def normalize_tokens(cls, value: object) -> object:
        return _strip_env_wrappers(value)

    @property
    def allowed_user_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_user_emails.split(",") if e.strip()]

    @property
    def trusted_proxy_ip_list(self) -> list[str]:
        return [ip.strip() for ip in self.trusted_proxy_ips.split(",") if ip.strip()]

    @property
    def default_desk_name_list(self) -> list[str]:
        return [n.strip() for n in self.tiflux_default_desk_names.split(",") if n.strip()]


def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Mantido para compatibilidade com testes; settings não são mais cacheadas."""
