from functools import lru_cache

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
    user_agent: str = "IntegracaoTifluxVHSYS/1.0"

    @field_validator(
        "tiflux_api_token",
        "vhsys_access_token",
        "vhsys_secret_access_token",
        mode="before",
    )
    @classmethod
    def normalize_tokens(cls, value: object) -> object:
        return _strip_env_wrappers(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
