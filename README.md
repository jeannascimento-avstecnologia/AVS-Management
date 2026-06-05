# Integração CNPJ → TiFlux + VHSYS

Consulta dados públicos por CNPJ (BrasilAPI) e cadastra o cliente em **TiFlux** e **VHSYS** em paralelo.

## Pré-requisitos

- Python 3.11+
- Tokens:
  - **TiFlux:** licença API por usuário → Configurações → Minha conta → Sessões → Gerar token
  - **VHSYS:** Minhas Integrações → Integração via API → Access-Token e Secret-Access-Token

## Instalação

```bash
cd c:\Projetos\Integracao_Tiflux_VHSYS
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` com seus tokens.

## Executar

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000 — informe o CNPJ e clique em **Cadastrar**.

API: `POST /integrar` com `cnpj` (form ou JSON `{"cnpj": "..."}`).

## Testes

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

Testes de integração real (exige `.env` preenchido):

```bash
pytest tests/ -v -m integration
```

## Documentação

Ver [ARQUITETURA.md](ARQUITETURA.md).
