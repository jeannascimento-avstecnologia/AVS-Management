from __future__ import annotations

PERMISSION_CADASTRAR = "cadastrar"
PERMISSION_INATIVAR = "inativar"
PERMISSION_CONSULTAR = "consultar"
PERMISSION_EMPRESAS_INATIVAS = "empresas_inativas"
PERMISSION_MANAGE_USERS = "manage_users"
PERMISSION_ORCAMENTOS = "orcamentos"
PERMISSION_APROVAR_ORCAMENTO = "aprovar_orcamento"
PERMISSION_GERAR_CONTRATO = "gerar_contrato"
PERMISSION_FATURAR = "faturar"
PERMISSION_APROVAR_FATURA = "aprovar_fatura"

ALL_PERMISSIONS: tuple[str, ...] = (
    PERMISSION_CADASTRAR,
    PERMISSION_INATIVAR,
    PERMISSION_CONSULTAR,
    PERMISSION_EMPRESAS_INATIVAS,
    PERMISSION_MANAGE_USERS,
    PERMISSION_ORCAMENTOS,
    PERMISSION_APROVAR_ORCAMENTO,
    PERMISSION_GERAR_CONTRATO,
    PERMISSION_FATURAR,
    PERMISSION_APROVAR_FATURA,
)

PERMISSION_LABELS: dict[str, str] = {
    PERMISSION_CADASTRAR: "Cadastrar clientes",
    PERMISSION_INATIVAR: "Inativar clientes",
    PERMISSION_CONSULTAR: "Consultar status",
    PERMISSION_EMPRESAS_INATIVAS: "Empresas sem atividade",
    PERMISSION_MANAGE_USERS: "Gerenciar usuários",
    PERMISSION_ORCAMENTOS: "Orçamentos",
    PERMISSION_APROVAR_ORCAMENTO: "Aprovar orçamento",
    PERMISSION_GERAR_CONTRATO: "Gerar contrato",
    PERMISSION_FATURAR: "Faturar",
    PERMISSION_APROVAR_FATURA: "Aprovar fatura",
}


def all_permissions_enabled() -> dict[str, bool]:
    return {key: True for key in ALL_PERMISSIONS}


def empty_permissions() -> dict[str, bool]:
    return {key: False for key in ALL_PERMISSIONS}
