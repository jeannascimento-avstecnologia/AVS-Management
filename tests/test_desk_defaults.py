from src.orchestrator import resolve_default_desk_ids


def test_resolve_default_desk_ids_by_name():
    desks = [
        {"id": 1, "name": "COMERCIAL", "display_name": "COMERCIAL / PROJETOS", "active": True},
        {"id": 2, "name": "VENDAS", "display_name": "VENDAS", "active": True},
        {"id": 3, "name": "OUTRA", "display_name": "OUTRA", "active": True},
        {"id": 4, "name": "SERVICOS", "display_name": "Serviços Avulsos", "active": True},
        {"id": 5, "name": "INATIVA", "display_name": "INATIVA", "active": False},
    ]
    ids = resolve_default_desk_ids(desks, ["Comercial", "Serviços Avulsos", "Vendas"])
    assert ids == [1, 4, 2]
