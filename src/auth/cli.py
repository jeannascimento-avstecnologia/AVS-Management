from __future__ import annotations

import argparse
import secrets
import sys

from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password, validate_password_policy
from src.config import clear_settings_cache, get_settings

SEED_USERS = [
    ("andre@avs.com.br", "André"),
    ("susana@avs.com.br", "Susana"),
    ("aline@avs.com.br", "Aline"),
    ("lucas.silva@avs.com.br", "Lucas Silva"),
]


def _temp_password() -> str:
    n = secrets.randbelow(900) + 100
    return f"Avs{n}x"


def cmd_seed(_: argparse.Namespace) -> int:
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    created: list[tuple[str, str]] = []
    skipped: list[str] = []

    emails_from_env = settings.allowed_user_email_list
    users_to_seed = SEED_USERS
    if emails_from_env:
        known = {e: n for e, n in SEED_USERS}
        users_to_seed = [
            (email, known.get(email, email.split("@")[0].replace(".", " ").title()))
            for email in emails_from_env
        ]

    for email, name in users_to_seed:
        if db.get_user_by_email(email):
            skipped.append(email)
            continue
        temp = _temp_password()
        db.create_user(email, name, hash_password(temp))
        created.append((email, temp))

    if created:
        print("Usuários criados:")
        for email, temp in created:
            print(f"  {email}  |  senha temporária: {temp}")
        print("\nPeça que cada usuário troque a senha após o primeiro acesso.")
    if skipped:
        print("Já existiam:", ", ".join(skipped))
    if not created and not skipped:
        print("Nenhum usuário para criar.")
    return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    email = args.email.strip().lower()
    if db.get_user_by_email(email):
        print(f"Usuário já existe: {email}", file=sys.stderr)
        return 1

    password = args.password or _temp_password()
    errors = validate_password_policy(password)
    if errors:
        print(errors[0], file=sys.stderr)
        return 1

    db.create_user(email, args.name, hash_password(password))
    print(f"Criado: {email}")
    if not args.password:
        print(f"Senha temporária: {password}")
    return 0


def cmd_list_users(_: argparse.Namespace) -> int:
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    users = db.list_users()
    if not users:
        print("Nenhum usuário cadastrado.")
        return 0
    for user in users:
        status = "ativo" if user.is_active else "inativo"
        print(f"{user.id:>3}  {user.email:<30}  {user.name:<20}  {status}")
    return 0


def cmd_reset_password(args: argparse.Namespace) -> int:
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    email = args.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        print(f"Usuário não encontrado: {email}", file=sys.stderr)
        return 1

    password = args.password or _temp_password()
    errors = validate_password_policy(password)
    if errors:
        print(errors[0], file=sys.stderr)
        return 1

    db.update_password(user.id, hash_password(password))
    db.revoke_remember_tokens(user.id)
    print(f"Senha atualizada para {email}")
    if not args.password:
        print(f"Nova senha temporária: {password}")
    return 0


def main(argv: list[str] | None = None) -> int:
    clear_settings_cache()
    parser = argparse.ArgumentParser(description="Administração de usuários locais — AVS Management")
    sub = parser.add_subparsers(dest="command", required=True)

    seed_parser = sub.add_parser("seed", help="Cria usuários iniciais com senhas temporárias")
    seed_parser.set_defaults(func=cmd_seed)

    create_parser = sub.add_parser("create-user", help="Cria um usuário")
    create_parser.add_argument("email")
    create_parser.add_argument("name")
    create_parser.add_argument("--password", help="Senha (mín. 5, com maiúscula, minúscula e número); omitir gera temporária")
    create_parser.set_defaults(func=cmd_create_user)

    list_parser = sub.add_parser("list-users", help="Lista usuários")
    list_parser.set_defaults(func=cmd_list_users)

    reset_parser = sub.add_parser("reset-password", help="Define nova senha para um usuário")
    reset_parser.add_argument("email")
    reset_parser.add_argument("--password", help="Nova senha; omitir gera temporária")
    reset_parser.set_defaults(func=cmd_reset_password)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
