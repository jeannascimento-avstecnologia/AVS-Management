from __future__ import annotations

PERMISSION_CADASTRAR = "cadastrar"
PERMISSION_INATIVAR = "inativar"
PERMISSION_CONSULTAR = "consultar"
PERMISSION_EMPRESAS_INATIVAS = "empresas_inativas"
PERMISSION_MANAGE_USERS = "manage_users"

ALL_PERMISSIONS: tuple[str, ...] = (
    PERMISSION_CADASTRAR,
    PERMISSION_INATIVAR,
    PERMISSION_CONSULTAR,
    PERMISSION_EMPRESAS_INATIVAS,
    PERMISSION_MANAGE_USERS,
)

PERMISSION_LABELS: dict[str, str] = {
    PERMISSION_CADASTRAR: "Cadastrar clientes",
    PERMISSION_INATIVAR: "Inativar clientes",
    PERMISSION_CONSULTAR: "Consultar status",
    PERMISSION_EMPRESAS_INATIVAS: "Empresas sem atividade",
    PERMISSION_MANAGE_USERS: "Gerenciar usuários",
}


def all_permissions_enabled() -> dict[str, bool]:
    return {key: True for key in ALL_PERMISSIONS}


def empty_permissions() -> dict[str, bool]:
    return {key: False for key in ALL_PERMISSIONS}
