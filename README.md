# AVS Management

Painel web para integração CNPJ → **TiFlux** + **VHSYS**: consulta BrasilAPI, cadastro, inativação, consulta de status e relatório de empresas sem atividade.

Repositório: [github.com/JeanLuengo/AVS-Management](https://github.com/JeanLuengo/AVS-Management)

```bash
git clone https://github.com/JeanLuengo/AVS-Management.git
cd AVS-Management
```

Pasta local sugerida: `c:\Projetos\AVS-Management` (Windows) ou `/opt/AVS-Management` (servidor Linux).

## Pré-requisitos

- Python 3.11+
- Tokens:
  - **TiFlux:** licença API por usuário → Configurações → Minha conta → Sessões → Gerar token
  - **VHSYS:** Minhas Integrações → Integração via API → Access-Token e Secret-Access-Token

## Instalação

```bash
cd c:\Projetos\AVS-Management
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` com seus tokens.

### Autenticação local (e-mail + senha)

1. Configure `AUTH_ENABLED=true`, `AUTH_PROVIDER=local` e as variáveis SMTP no `.env`.
2. Crie os usuários iniciais:

```bash
python -m src.auth.cli seed
```

3. Distribua as senhas temporárias exibidas no terminal.
4. Política de senha: mínimo **5 caracteres**, com letras maiúsculas, minúsculas e números. **Sem expiração** periódica.
5. Recuperação de senha: tela **Esqueci minha senha** envia link por e-mail (SMTP M365).

Comandos úteis:

```bash
python -m src.auth.cli list-users
python -m src.auth.cli create-user email@avs.com.br "Nome Completo"
python -m src.auth.cli reset-password email@avs.com.br
```

## Executar

### Desenvolvimento local (API + frontend com hot reload)

Na raiz do projeto:

```bash
npm run dev:local
```

Abra http://127.0.0.1:5173 — o Vite faz proxy das rotas da API para a porta 8000.

Requisitos: `.venv` criado, `pip install -r requirements.txt` e `.env` configurado.

### Produção / só API

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

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
