INDEX_HTML = """<!DOCTYPE html>

<html lang="pt-BR">

<head>

  <meta charset="utf-8">

  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>AVS Management</title>

  <link rel="icon" href="/static/logo-avs.png" type="image/png">

  <link rel="preconnect" href="https://fonts.googleapis.com">

  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>

    :root {

      --avs-navy: #0c1e3a;

      --avs-blue: #1a4f8c;

      --avs-accent: #2b8fd9;

      --avs-accent-hover: #1f7bc4;

      --avs-bg: #eef2f7;

      --avs-card: #ffffff;

      --avs-border: #d8e0ea;

      --avs-text: #1e293b;

      --avs-muted: #64748b;

      --avs-success: #0f766e;

      --avs-success-bg: #ecfdf5;

      --avs-error: #b91c1c;

      --avs-error-bg: #fef2f2;

      --avs-warn: #b45309;

      --avs-warn-bg: #fffbeb;

      --radius: 12px;

      --shadow: 0 8px 30px rgba(12, 30, 58, 0.08);

    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {

      font-family: 'Inter', system-ui, sans-serif;

      background: var(--avs-bg);

      color: var(--avs-text);

      min-height: 100vh;

      line-height: 1.5;

    }

    .topbar {

      background: linear-gradient(135deg, #f0f7ff 0%, #dbeafe 55%, #bfdbfe 100%);

      color: var(--avs-navy);

      padding: 1rem 1.5rem;

      box-shadow: 0 2px 12px rgba(26, 79, 140, 0.1);

      border-bottom: 1px solid rgba(26, 79, 140, 0.12);

    }

    .topbar-inner {

      max-width: 880px;

      margin: 0 auto;

      display: flex;

      align-items: center;

      justify-content: space-between;

      gap: 1rem;

    }

    .brand { display: flex; align-items: center; gap: 0.75rem; }

    .brand-mark {

      flex-shrink: 0;

      display: flex; align-items: center; justify-content: center;

      background: transparent;

      border-radius: 8px;

      overflow: hidden;

    }

    .brand-logo {

      height: 48px;

      width: auto;

      max-width: 160px;

      display: block;

      object-fit: contain;

    }

    .brand h1 { font-size: 1.1rem; font-weight: 700; color: var(--avs-navy); }

    .brand p { font-size: 0.78rem; color: var(--avs-muted); margin-top: 0.1rem; }

    .btn-ghost {

      background: transparent; border: 1px solid rgba(12, 30, 58, 0.22);

      color: var(--avs-navy); padding: 0.45rem 0.9rem; border-radius: 8px;

      font-size: 0.85rem; cursor: pointer; font-family: inherit;

    }

    .btn-ghost:hover { background: rgba(12, 30, 58, 0.06); }

    .wrap { max-width: 880px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }

    .card {

      background: var(--avs-card);

      border-radius: var(--radius);

      box-shadow: var(--shadow);

      border: 1px solid var(--avs-border);

      padding: 1.75rem;

    }

    .card-title { font-size: 1.35rem; font-weight: 700; color: var(--avs-navy); margin-bottom: 0.35rem; }

    .card-sub { color: var(--avs-muted); font-size: 0.92rem; margin-bottom: 1.5rem; }

    .panel { display: none; }

    .panel.active { display: block; }

    .steps {

      display: flex; gap: 0.5rem; flex-wrap: wrap;

      margin-bottom: 1.5rem;

    }

    .step {

      padding: 0.4rem 0.85rem; border-radius: 999px;

      background: #e2e8f0; color: var(--avs-muted);

      font-size: 0.8rem; font-weight: 600;

    }

    .step.active { background: var(--avs-accent); color: #fff; }

    .step.done { background: var(--avs-blue); color: #fff; }

    .menu-grid {

      display: grid;

      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));

      gap: 1rem;

    }

    .menu-item {

      border: 1px solid var(--avs-border);

      border-radius: var(--radius);

      padding: 1.25rem;

      cursor: pointer;

      transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;

      background: #fafbfc;

    }

    .menu-item:hover:not(.disabled) {

      border-color: var(--avs-accent);

      box-shadow: 0 4px 16px rgba(43, 143, 217, 0.15);

      transform: translateY(-2px);

    }

    .menu-item.disabled { opacity: 0.55; cursor: not-allowed; }

    .menu-item.menu-danger:hover:not(.disabled) {

      border-color: #fecaca;

      box-shadow: 0 4px 16px rgba(185, 28, 28, 0.12);

    }

    .menu-icon.danger { background: var(--avs-error-bg); color: var(--avs-error); }

    .btn-danger { background: var(--avs-error); color: #fff; }

    .btn-danger:hover:not(:disabled) { background: #991b1b; }

    .match-list {

      border: 1px solid var(--avs-border); border-radius: 8px;

      padding: 0.75rem; margin-top: 0.5rem; background: #fafbfc;

    }

    .match-item {

      display: flex; align-items: flex-start; gap: 0.55rem;

      padding: 0.5rem 0; border-bottom: 1px solid var(--avs-border);

      font-size: 0.88rem;

    }

    .match-item:last-child { border-bottom: none; }

    .match-item input { margin-top: 0.25rem; accent-color: var(--avs-error); }

    .match-item small { color: var(--avs-muted); display: block; font-size: 0.78rem; }

    .skip-row { margin-top: 0.5rem; font-size: 0.88rem; }

    .menu-icon.info { background: #e0f2fe; color: var(--avs-blue); }

    .consult-report-grid {

      display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;

    }

    @media (max-width: 720px) { .consult-report-grid { grid-template-columns: 1fr; } }

    .consult-col {

      border: 1px solid var(--avs-border); border-radius: 8px;

      padding: 1rem; background: #fafbfc; font-size: 0.85rem;

    }

    .consult-col h3 { font-size: 0.95rem; color: var(--avs-navy); margin-bottom: 0.75rem; }

    .kv-block { margin-bottom: 1rem; }

    .kv-block h4 { font-size: 0.82rem; color: var(--avs-blue); margin-bottom: 0.4rem; }

    .report-section { margin-bottom: 1rem; }

    .report-section h4 { font-size: 0.82rem; color: var(--avs-blue); margin-bottom: 0.4rem; }

    .report-dl { display: grid; grid-template-columns: minmax(140px, 42%) 1fr; gap: 0.35rem 0.75rem; margin: 0; }

    .report-dl dt { font-weight: 600; color: var(--avs-muted); font-size: 0.82rem; word-break: break-word; }

    .report-dl dd { margin: 0; font-size: 0.85rem; word-break: break-word; }

    .report-list { margin: 0; padding-left: 1.1rem; }

    .report-list li { margin-bottom: 0.2rem; }

    .subsection-label { font-size: 0.78rem; font-weight: 600; color: var(--avs-muted); margin: 0.75rem 0 0.35rem; text-transform: uppercase; letter-spacing: 0.03em; }

    @media print {

      .topbar, .steps, .actions, .no-print { display: none !important; }

      body { background: #fff; }

      .card { box-shadow: none; border: none; }

      .consult-col { break-inside: avoid; page-break-inside: avoid; }

      .consult-report-grid { grid-template-columns: 1fr; }

    }

    .menu-item h3 { font-size: 1rem; color: var(--avs-navy); margin-bottom: 0.35rem; }

    .menu-item p { font-size: 0.85rem; color: var(--avs-muted); }

    .menu-icon {

      width: 44px; height: 44px; border-radius: 10px;

      background: linear-gradient(135deg, var(--avs-accent), var(--avs-blue));

      color: #fff; display: flex; align-items: center; justify-content: center;

      font-size: 1.2rem; margin-bottom: 0.75rem;

    }

    label {

      display: block; margin: 0.85rem 0 0.35rem;

      font-weight: 600; font-size: 0.82rem; color: var(--avs-navy);

    }

    input[type=text], input[type=email], input[type=tel] {

      width: 100%; padding: 0.7rem 0.85rem; font-size: 0.95rem;

      border: 1px solid var(--avs-border); border-radius: 8px;

      font-family: inherit; transition: border-color 0.2s, box-shadow 0.2s;

    }

    input:focus {

      outline: none; border-color: var(--avs-accent);

      box-shadow: 0 0 0 3px rgba(43, 143, 217, 0.2);

    }

    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }

    @media (max-width: 600px) { .grid2 { grid-template-columns: 1fr; } }

    .checks {

      border: 1px solid var(--avs-border); border-radius: 8px;

      padding: 0.75rem; max-height: 200px; overflow-y: auto;

      background: #fafbfc;

    }

    .check-item {

      display: flex; align-items: flex-start; gap: 0.55rem;

      padding: 0.45rem 0; font-size: 0.88rem;

    }

    .check-item input { margin-top: 0.25rem; accent-color: var(--avs-accent); }

    .check-item small { color: var(--avs-muted); display: block; font-size: 0.78rem; }

    .section-title {

      font-size: 0.95rem; font-weight: 700; color: var(--avs-navy);

      margin: 1.5rem 0 0.5rem; padding-bottom: 0.4rem;

      border-bottom: 2px solid var(--avs-bg);

    }

    .section-title:first-of-type { margin-top: 0; }

    .hint { font-size: 0.8rem; color: var(--avs-muted); margin-top: 0.2rem; }

    .actions { display: flex; gap: 0.75rem; margin-top: 1.5rem; flex-wrap: wrap; }

    button {

      padding: 0.75rem 1.35rem; font-size: 0.95rem; font-weight: 600;

      border: none; border-radius: 8px; cursor: pointer; font-family: inherit;

      transition: background 0.2s, transform 0.1s;

    }

    .btn-primary { background: var(--avs-accent); color: #fff; }

    .btn-primary:hover:not(:disabled) { background: var(--avs-accent-hover); }

    .btn-secondary { background: #e2e8f0; color: var(--avs-navy); }

    .btn-secondary:hover:not(:disabled) { background: #cbd5e1; }

    button:disabled { opacity: 0.55; cursor: not-allowed; }

    .alert {

      display: flex; gap: 0.75rem; align-items: flex-start;

      padding: 0.9rem 1rem; border-radius: 8px;

      font-size: 0.88rem; margin-bottom: 1rem;

    }

    .alert[hidden] { display: none !important; }

    .alert-error { background: var(--avs-error-bg); border: 1px solid #fecaca; color: var(--avs-error); }

    .alert-warn { background: var(--avs-warn-bg); border: 1px solid #fde68a; color: var(--avs-warn); }

    .alert-success { background: var(--avs-success-bg); border: 1px solid #a7f3d0; color: var(--avs-success); }

    .alert-icon { font-size: 1.1rem; line-height: 1.3; flex-shrink: 0; }

    .alert-body strong { display: block; margin-bottom: 0.2rem; }

    .result-box {

      text-align: center; padding: 2rem 1rem;

    }

    .result-icon {

      width: 64px; height: 64px; border-radius: 50%;

      display: flex; align-items: center; justify-content: center;

      margin: 0 auto 1rem; font-size: 1.75rem; font-weight: 700;

    }

    .result-icon.ok { background: var(--avs-success-bg); color: var(--avs-success); }

    .result-icon.err { background: var(--avs-error-bg); color: var(--avs-error); }

    .result-icon.partial { background: var(--avs-warn-bg); color: var(--avs-warn); }

    .result-title { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem; }

    .result-title.ok { color: var(--avs-success); }

    .result-title.err { color: var(--avs-error); }

    .result-title.partial { color: var(--avs-warn); }

    .result-detail {

      color: var(--avs-muted); font-size: 0.92rem;

      max-width: 520px; margin: 0 auto 1rem; line-height: 1.6;

    }

    .result-detail.err { color: var(--avs-error); }

    .result-systems {

      display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap;

      margin-top: 1rem;

    }

    .sys-badge {

      padding: 0.4rem 0.85rem; border-radius: 999px;

      font-size: 0.8rem; font-weight: 600;

    }

    .sys-badge.ok { background: var(--avs-success-bg); color: var(--avs-success); }

    .sys-badge.err { background: var(--avs-error-bg); color: var(--avs-error); }

    .sys-badge.skip { background: #e0f2fe; color: var(--avs-blue); }

    .checkbox-row {

      display: flex; align-items: center; gap: 0.5rem;

      margin-top: 0.85rem; font-size: 0.9rem;

    }

    .checkbox-row input { accent-color: var(--avs-accent); width: auto; }

    .footer-note {

      text-align: center; margin-top: 2rem;

      font-size: 0.78rem; color: var(--avs-muted);

    }

  </style>

</head>

<body>

  <header class="topbar">

    <div class="topbar-inner">

      <div class="brand">

        <div class="brand-mark">

          <img src="/static/logo-avs.png" alt="AVS Tecnologia" class="brand-logo">

        </div>

        <div>

          <h1>Integrações AVS</h1>

          <p>TiFlux · VHSYS · BrasilAPI</p>

        </div>

      </div>

      <button type="button" class="btn-ghost" id="btnHomeTop" hidden>Início</button>

    </div>

  </header>



  <main class="wrap">

    <!-- TELA INICIAL -->

    <section id="panelHome" class="panel active">

      <div class="card">

        <h2 class="card-title">Central de integrações</h2>

        <p class="card-sub">Selecione uma operação. Novas funcionalidades serão adicionadas aqui.</p>

        <div class="menu-grid">

          <div class="menu-item" id="menuCadastrar" role="button" tabindex="0">

            <div class="menu-icon">+</div>

            <h3>Cadastrar Cliente</h3>

            <p>Consulta CNPJ, revisão dos dados e cadastro em TiFlux e VHSYS.</p>

          </div>

          <div class="menu-item menu-danger" id="menuExcluir" role="button" tabindex="0">

            <div class="menu-icon danger">×</div>

            <h3>Excluir Clientes</h3>

            <p>Busca por CNPJ ou nome e remove em TiFlux e VHSYS.</p>

          </div>

          <div class="menu-item" id="menuConsulta" role="button" tabindex="0">

            <div class="menu-icon info">?</div>

            <h3>Consulta status do cliente</h3>

            <p>Relatório completo do cadastro em TiFlux e VHSYS (mesas, grupos, categorias).</p>

          </div>

        </div>

      </div>

      <p class="footer-note">AVS Tecnologia · AVS Management</p>

    </section>



    <!-- FLUXO CADASTRO -->

    <section id="panelFlow" class="panel">

      <div class="steps" id="stepsBar">

        <span class="step active" data-step="1">1. CNPJ</span>

        <span class="step" data-step="2">2. Revisão</span>

        <span class="step" data-step="3">3. Resultado</span>

      </div>



      <!-- Passo 1: CNPJ -->

      <div id="subPanel1" class="card panel active">

        <h2 class="card-title">Informe o CNPJ</h2>

        <p class="card-sub">Os dados serão consultados na Receita Federal via BrasilAPI.</p>

        <div id="alertCnpj" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Não foi possível continuar</strong><span id="alertCnpjText"></span></div>

        </div>

        <form id="formCnpj">

          <label for="cnpj">CNPJ da empresa</label>

          <input id="cnpj" name="cnpj" placeholder="00.000.000/0000-00" required autocomplete="off">

          <div class="actions">

            <button type="button" class="btn-secondary" id="btnCancelarCnpj">Cancelar</button>

            <button type="submit" class="btn-primary" id="btnAvancar">Avançar</button>

          </div>

        </form>

      </div>



      <!-- Passo 2: Revisão -->

      <div id="subPanel2" class="card panel">

        <h2 class="card-title">Revise e confirme</h2>

        <p class="card-sub">Ajuste os dados antes de cadastrar nos sistemas.</p>

        <div id="receitaWarn" class="alert alert-warn" hidden>

          <span class="alert-icon">⚠</span>

          <div class="alert-body"><strong>Situação na Receita Federal</strong><span id="receitaWarnText"></span></div>

        </div>

        <div id="dupWarn" class="alert alert-warn" hidden>

          <span class="alert-icon">⚠</span>

          <div class="alert-body"><strong>Cliente já existente</strong><span id="dupWarnText"></span></div>

        </div>

        <div id="alertReview" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Verifique os dados</strong><span id="alertReviewText"></span></div>

        </div>

        <form id="formReview">

          <div class="section-title">Identificação</div>

          <label for="trade_name">Nome fantasia</label>

          <input id="trade_name" name="trade_name" required>

          <label for="legal_name">Razão social</label>

          <input id="legal_name" name="legal_name" required>

          <input type="hidden" id="cnpj_digits">

          <input type="hidden" id="cnpj_formatted">

          <input type="hidden" id="registration_status">

          <div class="grid2">

            <div><label for="phone">Telefone</label><input id="phone" name="phone" type="tel"></div>

            <div><label for="email">E-mail</label><input id="email" name="email" type="email"></div>

          </div>

          <p class="hint" id="receitaStatusHint"></p>

          <label class="checkbox-row"><input type="checkbox" id="status_active" checked> Cliente ativo no TiFlux e VHSYS</label>

          <label class="checkbox-row" id="overrideRow" hidden>

            <input type="checkbox" id="override_inactive_registration">

            Autorizo cadastro apesar da situação na Receita Federal

          </label>



          <div class="section-title">Endereço</div>

          <label for="street">Logradouro</label><input id="street" name="street">

          <div class="grid2">

            <div><label for="number">Número</label><input id="number" name="number"></div>

            <div><label for="complement">Complemento</label><input id="complement" name="complement"></div>

          </div>

          <div class="grid2">

            <div><label for="district">Bairro</label><input id="district" name="district"></div>

            <div><label for="zip_code">CEP</label><input id="zip_code" name="zip_code"></div>

          </div>

          <div class="grid2">

            <div><label for="city">Cidade</label><input id="city" name="city"></div>

            <div><label for="state">UF</label><input id="state" name="state" maxlength="2"></div>

          </div>



          <div class="section-title">TiFlux — Mesas de serviço</div>

          <p class="hint">Selecione as mesas para o cliente aparecer no painel.</p>

          <div id="desksBox" class="checks"></div>



          <div class="section-title">TiFlux — Grupos de atendentes</div>

          <p class="hint">Necessário para o relacionamento com equipes.</p>

          <div id="groupsBox" class="checks"></div>



          <div class="actions">

            <button type="button" class="btn-secondary" id="btnVoltar">Voltar</button>

            <button type="submit" class="btn-primary" id="btnConfirmar">Confirmar cadastro</button>

          </div>

        </form>

      </div>



      <!-- Passo 3: Resultado -->

      <div id="subPanel3" class="card panel">

        <div class="result-box" id="resultBox"></div>

        <div class="actions" style="justify-content:center;">

          <button type="button" class="btn-secondary" id="btnInicio">Voltar ao início</button>

          <button type="button" class="btn-primary" id="btnNovo">Novo cadastro</button>

        </div>

      </div>

    </section>



    <!-- FLUXO EXCLUSÃO -->

    <section id="panelDeleteFlow" class="panel">

      <div class="steps" id="stepsDeleteBar">

        <span class="step active" data-delete-step="1">1. Busca</span>

        <span class="step" data-delete-step="2">2. Conferência</span>

        <span class="step" data-delete-step="3">3. Resultado</span>

      </div>



      <div id="deleteSubPanel1" class="card panel active">

        <h2 class="card-title">Excluir cliente</h2>

        <p class="card-sub">Informe o CNPJ ou o nome (razão social / fantasia) do cliente.</p>

        <div id="alertDeleteSearch" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Não foi possível continuar</strong><span id="alertDeleteSearchText"></span></div>

        </div>

        <form id="formDeleteSearch">

          <label for="delete_query">CNPJ ou nome do cliente</label>

          <input id="delete_query" name="query" placeholder="00.000.000/0000-00 ou razão social" required autocomplete="off">

          <div class="actions">

            <button type="button" class="btn-secondary" id="btnCancelarDelete">Cancelar</button>

            <button type="submit" class="btn-primary" id="btnBuscarDelete">Buscar</button>

          </div>

        </form>

      </div>



      <div id="deleteSubPanel2" class="card panel">

        <h2 class="card-title">Conferir antes de excluir</h2>

        <p class="card-sub">Selecione o registro em cada sistema. TiFlux remove permanentemente; VHSYS envia à lixeira.</p>

        <div id="alertDeleteReview" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Verifique a seleção</strong><span id="alertDeleteReviewText"></span></div>

        </div>

        <div class="section-title">TiFlux</div>

        <div id="tifluxMatchesBox" class="match-list"></div>

        <label class="checkbox-row skip-row" id="skipTifluxRow" hidden>

          <input type="checkbox" id="skip_tiflux"> Não excluir no TiFlux

        </label>



        <div class="section-title">VHSYS</div>

        <div id="vhsysMatchesBox" class="match-list"></div>

        <label class="checkbox-row skip-row" id="skipVhsysRow" hidden>

          <input type="checkbox" id="skip_vhsys"> Não excluir no VHSYS

        </label>



        <label class="checkbox-row" style="margin-top:1rem;">

          <input type="checkbox" id="confirmDeleteAck">

          Entendo que a exclusão no TiFlux é irreversível e no VHSYS envia o cliente à lixeira.

        </label>



        <div class="actions">

          <button type="button" class="btn-secondary" id="btnVoltarDelete">Voltar</button>

          <button type="button" class="btn-danger" id="btnConfirmarDelete" disabled>Confirmar exclusão</button>

        </div>

      </div>



      <div id="deleteSubPanel3" class="card panel">

        <div class="result-box" id="deleteResultBox"></div>

        <div class="actions" style="justify-content:center;">

          <button type="button" class="btn-secondary" id="btnInicioDelete">Voltar ao início</button>

          <button type="button" class="btn-primary" id="btnNovaExclusao">Nova exclusão</button>

        </div>

      </div>

    </section>



    <!-- FLUXO CONSULTA STATUS -->

    <section id="panelConsultFlow" class="panel">

      <div class="steps" id="stepsConsultBar">

        <span class="step active" data-consult-step="1">1. Busca</span>

        <span class="step" data-consult-step="2">2. Seleção</span>

        <span class="step" data-consult-step="3">3. Relatório</span>

      </div>

      <div id="consultSubPanel1" class="card panel active">

        <h2 class="card-title">Consulta status do cliente</h2>

        <p class="card-sub">Informe CNPJ ou nome para carregar o cadastro completo em TiFlux e VHSYS.</p>

        <div id="alertConsultSearch" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Não foi possível continuar</strong><span id="alertConsultSearchText"></span></div>

        </div>

        <form id="formConsultSearch">

          <label for="consult_query">CNPJ ou nome do cliente</label>

          <input id="consult_query" name="query" placeholder="00.000.000/0000-00 ou razão social" required autocomplete="off">

          <div class="actions">

            <button type="button" class="btn-secondary" id="btnCancelarConsulta">Cancelar</button>

            <button type="submit" class="btn-primary" id="btnBuscarConsulta">Buscar</button>

          </div>

        </form>

      </div>

      <div id="consultSubPanel2" class="card panel">

        <h2 class="card-title">Selecionar registros</h2>

        <p class="card-sub">Escolha qual cliente consultar em cada sistema (ativos e lixeira no VHSYS).</p>

        <div id="alertConsultReview" class="alert alert-error" hidden>

          <span class="alert-icon">!</span>

          <div class="alert-body"><strong>Verifique a seleção</strong><span id="alertConsultReviewText"></span></div>

        </div>

        <div class="section-title">TiFlux</div>

        <div id="consultTifluxMatchesBox" class="match-list"></div>

        <label class="checkbox-row skip-row" id="skipTifluxConsultRow" hidden>

          <input type="checkbox" id="skip_tiflux_consult"> Não consultar TiFlux

        </label>

        <div class="section-title">VHSYS — Ativos</div>

        <div id="consultVhsysActiveBox" class="match-list"></div>

        <div class="section-title">VHSYS — Lixeira</div>

        <div id="consultVhsysTrashBox" class="match-list"></div>

        <label class="checkbox-row skip-row" id="skipVhsysConsultRow" hidden>

          <input type="checkbox" id="skip_vhsys_consult"> Não consultar VHSYS

        </label>

        <div class="actions">

          <button type="button" class="btn-secondary" id="btnVoltarConsulta">Voltar</button>

          <button type="button" class="btn-primary" id="btnConfirmarConsulta" disabled>Carregar relatório</button>

        </div>

      </div>

      <div id="consultSubPanel3" class="card panel">

        <div id="consultReportPrintArea">

          <h2 class="card-title">Relatório do cliente</h2>

          <p class="card-sub" id="consultReportQuery"></p>

          <div class="consult-report-grid" id="consultReportGrid"></div>

        </div>

        <div class="actions no-print" style="justify-content:center; flex-wrap:wrap; gap:0.5rem; margin-top:1rem;">

          <button type="button" class="btn-secondary" id="btnInicioConsulta">Voltar ao início</button>

          <button type="button" class="btn-secondary" id="btnImprimirConsulta">Imprimir / PDF</button>

          <button type="button" class="btn-primary" id="btnBaixarJsonConsulta">Baixar JSON</button>

          <button type="button" class="btn-primary" id="btnNovaConsulta">Nova consulta</button>

        </div>

      </div>

    </section>

  </main>



  <script>

    let previewData = null;

    let deletePreviewData = null;

    let consultPreviewData = null;

    let consultDetailData = null;



    const panelHome = document.getElementById('panelHome');

    const panelFlow = document.getElementById('panelFlow');

    const panelDeleteFlow = document.getElementById('panelDeleteFlow');

    const panelConsultFlow = document.getElementById('panelConsultFlow');

    const btnHomeTop = document.getElementById('btnHomeTop');

    const deleteSubPanels = [

      document.getElementById('deleteSubPanel1'),

      document.getElementById('deleteSubPanel2'),

      document.getElementById('deleteSubPanel3'),

    ];

    const deleteStepEls = document.querySelectorAll('#stepsDeleteBar .step');

    const consultSubPanels = [

      document.getElementById('consultSubPanel1'),

      document.getElementById('consultSubPanel2'),

      document.getElementById('consultSubPanel3'),

    ];

    const consultStepEls = document.querySelectorAll('#stepsConsultBar .step');

    const subPanels = [document.getElementById('subPanel1'), document.getElementById('subPanel2'), document.getElementById('subPanel3')];

    const stepEls = document.querySelectorAll('#stepsBar .step');



    function showHome() {

      panelHome.classList.add('active');

      panelFlow.classList.remove('active');

      panelDeleteFlow.classList.remove('active');

      panelConsultFlow.classList.remove('active');

      btnHomeTop.hidden = true;

    }



    function showFlow(step) {

      panelHome.classList.remove('active');

      panelFlow.classList.add('active');

      panelDeleteFlow.classList.remove('active');

      panelConsultFlow.classList.remove('active');

      btnHomeTop.hidden = false;

      subPanels.forEach((p, i) => p.classList.toggle('active', i + 1 === step));

      stepEls.forEach(el => {

        const n = Number(el.dataset.step);

        el.classList.toggle('active', n === step);

        el.classList.toggle('done', n < step);

      });

    }



    function showAlert(boxId, textId, message) {

      const box = document.getElementById(boxId);

      const text = document.getElementById(textId);

      if (!message) { box.hidden = true; return; }

      text.textContent = message;

      box.hidden = false;

      box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    }



    function hideAlerts() {

      ['alertCnpj', 'alertReview'].forEach(id => {

        const el = document.getElementById(id);

        if (el) el.hidden = true;

      });

    }



    function renderChecks(container, items, defaults) {

      container.innerHTML = '';

      if (!items.length) {

        container.innerHTML = '<p class="hint">Nenhuma opção retornada pela API TiFlux.</p>';

        return;

      }

      const defaultSet = new Set((defaults || []).map(Number));

      for (const item of items) {

        const id = Number(item.id);

        const label = document.createElement('label');

        label.className = 'check-item';

        const cb = document.createElement('input');

        cb.type = 'checkbox';

        cb.value = String(id);

        cb.checked = defaultSet.has(id);

        const text = document.createElement('span');

        const title = item.display_name || item.name || ('ID ' + id);

        text.innerHTML = '<strong>' + escapeHtml(title) + '</strong>' +

          (item.active === false ? '<small>Mesa inativa</small>' : '') +

          '<small>ID: ' + id + '</small>';

        label.appendChild(cb);

        label.appendChild(text);

        container.appendChild(label);

      }

    }



    function escapeHtml(s) {

      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

    }



    function fillCompany(c) {

      document.getElementById('cnpj_digits').value = c.cnpj_digits || '';

      document.getElementById('cnpj_formatted').value = c.cnpj_formatted || '';

      document.getElementById('trade_name').value = c.trade_name || '';

      document.getElementById('legal_name').value = c.legal_name || '';

      document.getElementById('phone').value = c.phone || '';

      document.getElementById('email').value = c.email || '';

      document.getElementById('status_active').checked = !!c.status_active;

      const receita = (c.registration_status || '').toUpperCase();

      document.getElementById('registration_status').value = receita;

      const hint = document.getElementById('receitaStatusHint');

      hint.textContent = receita

        ? 'Situação cadastral na Receita: ' + receita + '.'

        : '';

      const a = c.address || {};

      document.getElementById('street').value = a.street || '';

      document.getElementById('number').value = a.number || '';

      document.getElementById('complement').value = a.complement || '';

      document.getElementById('district').value = a.district || '';

      document.getElementById('city').value = a.city || '';

      document.getElementById('state').value = a.state || '';

      document.getElementById('zip_code').value = a.zip_code || '';

    }



    function collectPayload() {

      const desk_ids = [...document.querySelectorAll('#desksBox input:checked')].map(x => Number(x.value));

      const technical_group_ids = [...document.querySelectorAll('#groupsBox input:checked')].map(x => Number(x.value));

      return {

        company: {

          cnpj_digits: document.getElementById('cnpj_digits').value,

          cnpj_formatted: document.getElementById('cnpj_formatted').value,

          trade_name: document.getElementById('trade_name').value.trim(),

          legal_name: document.getElementById('legal_name').value.trim(),

          phone: document.getElementById('phone').value.trim(),

          email: document.getElementById('email').value.trim(),

          status_active: document.getElementById('status_active').checked,

          registration_status: document.getElementById('registration_status').value.trim().toUpperCase(),

          address: {

            street: document.getElementById('street').value.trim(),

            number: document.getElementById('number').value.trim(),

            complement: document.getElementById('complement').value.trim(),

            district: document.getElementById('district').value.trim(),

            city: document.getElementById('city').value.trim(),

            state: document.getElementById('state').value.trim(),

            zip_code: document.getElementById('zip_code').value.trim(),

          },

          cnae_fiscal: previewData?.company?.cnae_fiscal ?? null,

          cnae_description: previewData?.company?.cnae_description ?? '',

        },

        desk_ids,

        technical_group_ids,

        override_inactive_registration: document.getElementById('override_inactive_registration').checked,

      };

    }



    function renderResult(data) {

      const box = document.getElementById('resultBox');

      const tf = data.tiflux || {};

      const vh = data.vhsys || {};

      const company = data.company || {};

      const name = company.trade_name || company.legal_name || 'Cliente';



      let iconClass = 'err', titleClass = 'err', icon = '✕', title = 'Cadastro não concluído';

      let detail = '';



      if (data.success) {

        iconClass = titleClass = 'ok'; icon = '✓';

        title = 'Cliente cadastrado com sucesso';

        detail = '"' + escapeHtml(name) + '" foi registrado no TiFlux e no VHSYS.';

        if (tf.skipped && vh.skipped) {

          detail = 'O cliente "' + escapeHtml(name) + '" já existia em ambos os sistemas.';

        } else if (tf.skipped) {

          iconClass = titleClass = 'partial'; icon = '◐';

          title = 'Cadastro parcialmente concluído';

          detail = 'VHSYS: cadastrado. TiFlux: cliente já existia.';

        } else if (vh.skipped) {

          iconClass = titleClass = 'partial'; icon = '◐';

          title = 'Cadastro parcialmente concluído';

          detail = 'TiFlux: cadastrado. VHSYS: cliente já existia.';

        }

      } else if (data.partial) {

        iconClass = titleClass = 'partial'; icon = '◐';

        title = 'Cadastro parcialmente concluído';

        const parts = [];

        if (tf.success) parts.push('TiFlux: ' + (tf.message || 'OK'));

        else parts.push('TiFlux: ' + (tf.error || tf.message || 'Falha'));

        if (vh.success) parts.push('VHSYS: ' + (vh.message || 'OK'));

        else parts.push('VHSYS: ' + (vh.error || vh.message || 'Falha'));

        detail = parts.join('. ');

      } else {

        detail = data.error || tf.error || vh.error || 'Ocorreu um erro inesperado. Tente novamente ou contate o suporte.';

      }



      const badges = [];

      if (tf.success) badges.push('<span class="sys-badge ' + (tf.skipped ? 'skip' : 'ok') + '">TiFlux: ' + (tf.skipped ? 'já existia' : 'OK') + '</span>');

      else badges.push('<span class="sys-badge err">TiFlux: falhou</span>');

      if (vh.success) badges.push('<span class="sys-badge ' + (vh.skipped ? 'skip' : 'ok') + '">VHSYS: ' + (vh.skipped ? 'já existia' : 'OK') + '</span>');

      else badges.push('<span class="sys-badge err">VHSYS: falhou</span>');



      box.innerHTML =

        '<div class="result-icon ' + iconClass + '">' + icon + '</div>' +

        '<div class="result-title ' + titleClass + '">' + escapeHtml(title) + '</div>' +

        '<p class="result-detail ' + (data.success ? '' : 'err') + '">' + detail + '</p>' +

        '<div class="result-systems">' + badges.join('') + '</div>';

    }



    document.getElementById('menuCadastrar').addEventListener('click', () => {

      hideAlerts();

      document.getElementById('formCnpj').reset();

      previewData = null;

      document.getElementById('dupWarn').hidden = true;

      document.getElementById('receitaWarn').hidden = true;

      document.getElementById('overrideRow').hidden = true;

      showFlow(1);

    });

    document.getElementById('menuCadastrar').addEventListener('keydown', (e) => {

      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('menuCadastrar').click(); }

    });



    document.getElementById('btnHomeTop').addEventListener('click', showHome);

    document.getElementById('btnCancelarCnpj').addEventListener('click', showHome);

    document.getElementById('btnInicio').addEventListener('click', showHome);



    document.getElementById('formCnpj').addEventListener('submit', async (e) => {

      e.preventDefault();

      hideAlerts();

      const btn = document.getElementById('btnAvancar');

      btn.disabled = true;

      btn.textContent = 'Consultando...';

      const fd = new FormData(e.target);

      try {

        const res = await fetch('/preview', { method: 'POST', body: fd });

        let data;

        try { data = await res.json(); } catch { data = { error: 'Resposta inválida do servidor.' }; }

        if (!res.ok || data.success === false) {

          showAlert('alertCnpj', 'alertCnpjText', data.error || 'Não foi possível consultar o CNPJ. Verifique o número e tente novamente.');

          return;

        }

        previewData = data;

        fillCompany(data.company);

        const opts = data.tiflux_options || {};

        renderChecks(document.getElementById('desksBox'), opts.desks || [], opts.defaults?.desk_ids);

        renderChecks(document.getElementById('groupsBox'), opts.technical_groups || [], opts.defaults?.technical_group_ids);

        const receitaBox = document.getElementById('receitaWarn');

        if (data.warnings && data.warnings.length) {

          document.getElementById('receitaWarnText').textContent = ' ' + data.warnings.join(' ');

          receitaBox.hidden = false;

        } else {

          receitaBox.hidden = true;

        }

        const overrideRow = document.getElementById('overrideRow');

        const overrideCb = document.getElementById('override_inactive_registration');

        overrideRow.hidden = !data.requires_inactive_override;

        overrideCb.checked = false;

        const dup = data.duplicates || {};

        const dupBox = document.getElementById('dupWarn');

        if (dup.tiflux || dup.vhsys) {

          const parts = [];

          if (dup.tiflux) parts.push('TiFlux');

          if (dup.vhsys) parts.push('VHSYS');

          document.getElementById('dupWarnText').textContent = ' Já cadastrado em ' + parts.join(' e ') + '. O sistema ignorará esses destinos.';

          dupBox.hidden = false;

        } else {

          dupBox.hidden = true;

        }

        showFlow(2);

      } catch (err) {

        showAlert('alertCnpj', 'alertCnpjText', 'Falha de conexão. Verifique se o servidor está em execução.');

      } finally {

        btn.disabled = false;

        btn.textContent = 'Avançar';

      }

    });



    document.getElementById('btnVoltar').addEventListener('click', () => showFlow(1));



    document.getElementById('formReview').addEventListener('submit', async (e) => {

      e.preventDefault();

      document.getElementById('alertReview').hidden = true;

      const btn = document.getElementById('btnConfirmar');

      const payload = collectPayload();

      if (!payload.desk_ids.length) {

        showAlert('alertReview', 'alertReviewText', ' Selecione ao menos uma mesa de serviço no TiFlux.');

        return;

      }

      if (!payload.technical_group_ids.length) {

        showAlert('alertReview', 'alertReviewText', ' Selecione ao menos um grupo de atendentes no TiFlux.');

        return;

      }

      if (previewData?.requires_inactive_override && !payload.override_inactive_registration) {

        showAlert('alertReview', 'alertReviewText', ' Marque a autorização para cadastrar empresa com situação não ativa na Receita Federal.');

        return;

      }

      btn.disabled = true;

      btn.textContent = 'Cadastrando...';

      try {

        const res = await fetch('/integrar', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(payload),

        });

        let data;

        try { data = await res.json(); } catch { data = { success: false, error: 'Resposta inválida do servidor.' }; }

        renderResult(data);

        showFlow(3);

      } catch (err) {

        renderResult({ success: false, error: 'Falha de conexão com o servidor.' });

        showFlow(3);

      } finally {

        btn.disabled = false;

        btn.textContent = 'Confirmar cadastro';

      }

    });



    document.getElementById('btnNovo').addEventListener('click', () => {

      document.getElementById('formCnpj').reset();

      previewData = null;

      document.getElementById('dupWarn').hidden = true;

      document.getElementById('receitaWarn').hidden = true;

      document.getElementById('overrideRow').hidden = true;

      hideAlerts();

      showFlow(1);

    });



    function showDeleteFlow(step) {

      panelHome.classList.remove('active');

      panelFlow.classList.remove('active');

      panelDeleteFlow.classList.add('active');

      panelConsultFlow.classList.remove('active');

      btnHomeTop.hidden = false;

      deleteSubPanels.forEach((p, i) => p.classList.toggle('active', i + 1 === step));

      deleteStepEls.forEach(el => {

        const n = Number(el.dataset.deleteStep);

        el.classList.toggle('active', n === step);

        el.classList.toggle('done', n < step);

      });

    }



    function renderDeleteMatches(container, matches, system) {

      container.innerHTML = '';

      if (!matches.length) {

        container.innerHTML = '<p class="hint">Nenhum cliente encontrado.</p>';

        return;

      }

      const inputName = system === 'tiflux' ? 'tiflux_pick' : 'vhsys_pick';

      matches.forEach((m, idx) => {

        const label = document.createElement('label');

        label.className = 'match-item';

        const cb = document.createElement('input');

        cb.type = 'radio';

        cb.name = inputName;

        cb.value = String(system === 'tiflux' ? m.id : m.id);

        if (matches.length === 1) cb.checked = true;

        const text = document.createElement('span');

        if (system === 'tiflux') {

          text.innerHTML = '<strong>' + escapeHtml(m.name || m.social || 'Cliente') + '</strong>' +

            '<small>Razão social: ' + escapeHtml(m.social || '—') + '</small>' +

            '<small>CNPJ: ' + escapeHtml(formatCnpjDisplay(m.social_revenue)) + '</small>';

        } else {

          text.innerHTML = '<strong>' + escapeHtml(m.fantasia_cliente || m.razao_cliente || 'Cliente') + '</strong>' +

            '<small>Razão social: ' + escapeHtml(m.razao_cliente || '—') + '</small>' +

            '<small>CNPJ: ' + escapeHtml(formatCnpjDisplay(m.cnpj_cliente)) + (m.situacao_cliente ? ' · Situação: ' + escapeHtml(m.situacao_cliente) : '') + '</small>';

        }

        label.appendChild(cb);

        label.appendChild(text);

        container.appendChild(label);

      });

    }



    function updateDeleteConfirmButton() {

      const btn = document.getElementById('btnConfirmarDelete');

      const ack = document.getElementById('confirmDeleteAck').checked;

      const tf = deletePreviewData?.tiflux;

      const vh = deletePreviewData?.vhsys;

      let ok = ack && (tf?.found || vh?.found);

      if (tf?.found && !document.getElementById('skip_tiflux').checked) {

        ok = ok && !!document.querySelector('input[name="tiflux_pick"]:checked');

      }

      if (vh?.found && !document.getElementById('skip_vhsys').checked) {

        ok = ok && !!document.querySelector('input[name="vhsys_pick"]:checked');

      }

      btn.disabled = !ok;

    }



    function fillDeleteReview(data) {

      const tf = data.tiflux || {};

      const vh = data.vhsys || {};

      renderDeleteMatches(document.getElementById('tifluxMatchesBox'), tf.matches || [], 'tiflux');

      renderDeleteMatches(document.getElementById('vhsysMatchesBox'), vh.matches || [], 'vhsys');

      document.getElementById('skipTifluxRow').hidden = !tf.found;

      document.getElementById('skipVhsysRow').hidden = !vh.found;

      document.getElementById('skip_tiflux').checked = false;

      document.getElementById('skip_vhsys').checked = false;

      document.getElementById('confirmDeleteAck').checked = false;

      updateDeleteConfirmButton();

    }



    function renderDeleteResult(data) {

      const box = document.getElementById('deleteResultBox');

      const tf = data.tiflux || {};

      const vh = data.vhsys || {};

      let iconClass = 'err', titleClass = 'err', icon = '✕', title = 'Exclusão não concluída';

      let detail = data.error || tf.error || vh.error || 'Ocorreu um erro inesperado.';



      if (data.success) {

        iconClass = titleClass = 'ok'; icon = '✓';

        title = 'Exclusão concluída';

        detail = 'Operação finalizada nos sistemas selecionados.';

      } else if (data.partial) {

        iconClass = titleClass = 'partial'; icon = '◐';

        title = 'Exclusão parcial';

        const parts = [];

        if (tf.success) parts.push('TiFlux: ' + (tf.message || 'OK'));

        else if (!tf.skipped) parts.push('TiFlux: ' + (tf.error || tf.message || 'Falha'));

        if (vh.success) parts.push('VHSYS: ' + (vh.message || 'OK'));

        else if (!vh.skipped) parts.push('VHSYS: ' + (vh.error || vh.message || 'Falha'));

        detail = parts.join('. ');

      }



      const badges = [];

      if (tf.skipped) badges.push('<span class="sys-badge skip">TiFlux: ignorado</span>');

      else if (tf.success) badges.push('<span class="sys-badge ok">TiFlux: inativado</span>');

      else badges.push('<span class="sys-badge err">TiFlux: falhou</span>');

      if (vh.skipped) badges.push('<span class="sys-badge skip">VHSYS: ignorado</span>');

      else if (vh.success) badges.push('<span class="sys-badge ok">VHSYS: lixeira</span>');

      else badges.push('<span class="sys-badge err">VHSYS: falhou</span>');



      box.innerHTML =

        '<div class="result-icon ' + iconClass + '">' + icon + '</div>' +

        '<div class="result-title ' + titleClass + '">' + escapeHtml(title) + '</div>' +

        '<p class="result-detail ' + (data.success ? '' : 'err') + '">' + escapeHtml(detail) + '</p>' +

        '<div class="result-systems">' + badges.join('') + '</div>';

    }



    document.getElementById('menuExcluir').addEventListener('click', () => {

      deletePreviewData = null;

      document.getElementById('formDeleteSearch').reset();

      document.getElementById('alertDeleteSearch').hidden = true;

      document.getElementById('alertDeleteReview').hidden = true;

      showDeleteFlow(1);

    });

    document.getElementById('menuExcluir').addEventListener('keydown', (e) => {

      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('menuExcluir').click(); }

    });



    document.getElementById('btnCancelarDelete').addEventListener('click', showHome);

    document.getElementById('btnInicioDelete').addEventListener('click', showHome);



    document.getElementById('formDeleteSearch').addEventListener('submit', async (e) => {

      e.preventDefault();

      document.getElementById('alertDeleteSearch').hidden = true;

      const btn = document.getElementById('btnBuscarDelete');

      btn.disabled = true;

      btn.textContent = 'Buscando...';

      const query = document.getElementById('delete_query').value.trim();

      try {

        const res = await fetch('/excluir/preview', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ query }),

        });

        let data;

        try { data = await res.json(); } catch { data = { success: false, error: 'Resposta inválida.' }; }

        if (!res.ok || data.success === false) {

          showAlert('alertDeleteSearch', 'alertDeleteSearchText', ' ' + (data.error || 'Busca falhou.'));

          return;

        }

        if (!data.tiflux?.found && !data.vhsys?.found) {

          showAlert('alertDeleteSearch', 'alertDeleteSearchText', ' Nenhum cliente encontrado no TiFlux nem no VHSYS.');

          return;

        }

        deletePreviewData = data;

        deletePreviewData._rawQuery = query;

        fillDeleteReview(data);

        showDeleteFlow(2);

      } catch (err) {

        showAlert('alertDeleteSearch', 'alertDeleteSearchText', ' Falha de conexão com o servidor.');

      } finally {

        btn.disabled = false;

        btn.textContent = 'Buscar';

      }

    });



    ['confirmDeleteAck', 'skip_tiflux', 'skip_vhsys'].forEach(id => {

      document.getElementById(id).addEventListener('change', updateDeleteConfirmButton);

    });

    document.getElementById('tifluxMatchesBox').addEventListener('change', updateDeleteConfirmButton);

    document.getElementById('vhsysMatchesBox').addEventListener('change', updateDeleteConfirmButton);



    document.getElementById('btnVoltarDelete').addEventListener('click', () => showDeleteFlow(1));



    document.getElementById('btnConfirmarDelete').addEventListener('click', async () => {

      document.getElementById('alertDeleteReview').hidden = true;

      if (!deletePreviewData) return;

      const btn = document.getElementById('btnConfirmarDelete');

      const tfFound = deletePreviewData.tiflux?.found;

      const vhFound = deletePreviewData.vhsys?.found;

      let tifluxId = null;

      let vhsysId = null;

      if (tfFound && !document.getElementById('skip_tiflux').checked) {

        const picked = document.querySelector('input[name="tiflux_pick"]:checked');

        if (!picked) {

          showAlert('alertDeleteReview', 'alertDeleteReviewText', ' Selecione um cliente no TiFlux.');

          return;

        }

        tifluxId = Number(picked.value);

      }

      if (vhFound && !document.getElementById('skip_vhsys').checked) {

        const picked = document.querySelector('input[name="vhsys_pick"]:checked');

        if (!picked) {

          showAlert('alertDeleteReview', 'alertDeleteReviewText', ' Selecione um cliente no VHSYS.');

          return;

        }

        vhsysId = Number(picked.value);

      }

      if (tifluxId === null && vhsysId === null) {

        showAlert('alertDeleteReview', 'alertDeleteReviewText', ' Selecione ao menos um sistema para excluir.');

        return;

      }

      btn.disabled = true;

      btn.textContent = 'Excluindo...';

      try {

        const res = await fetch('/excluir', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            query: deletePreviewData._rawQuery || deletePreviewData.query,

            tiflux_client_id: tifluxId,

            vhsys_client_id: vhsysId,

          }),

        });

        let data;

        try { data = await res.json(); } catch { data = { success: false, error: 'Resposta inválida.' }; }

        renderDeleteResult(data);

        showDeleteFlow(3);

      } catch (err) {

        renderDeleteResult({ success: false, error: 'Falha de conexão com o servidor.' });

        showDeleteFlow(3);

      } finally {

        btn.disabled = false;

        btn.textContent = 'Confirmar exclusão';

        updateDeleteConfirmButton();

      }

    });



    document.getElementById('btnNovaExclusao').addEventListener('click', () => {

      deletePreviewData = null;

      document.getElementById('formDeleteSearch').reset();

      document.getElementById('alertDeleteSearch').hidden = true;

      document.getElementById('alertDeleteReview').hidden = true;

      showDeleteFlow(1);

    });



    function showConsultFlow(step) {

      panelHome.classList.remove('active');

      panelFlow.classList.remove('active');

      panelDeleteFlow.classList.remove('active');

      panelConsultFlow.classList.add('active');

      btnHomeTop.hidden = false;

      consultSubPanels.forEach((p, i) => p.classList.toggle('active', i + 1 === step));

      consultStepEls.forEach(el => {

        const n = Number(el.dataset.consultStep);

        el.classList.toggle('active', n === step);

        el.classList.toggle('done', n < step);

      });

    }



    function renderConsultMatches(container, matches, system, inputName) {

      container.innerHTML = '';

      if (!matches || !matches.length) {

        container.innerHTML = '<p class="hint">Nenhum cliente encontrado.</p>';

        return;

      }

      matches.forEach((m) => {

        const label = document.createElement('label');

        label.className = 'match-item';

        const cb = document.createElement('input');

        cb.type = 'radio';

        cb.name = inputName;

        cb.value = String(m.id);

        if (matches.length === 1) cb.checked = true;

        const text = document.createElement('span');

        if (system === 'tiflux') {

          text.innerHTML = '<strong>' + escapeHtml(m.name || m.social || 'Cliente') + '</strong>' +

            '<small>Razão social: ' + escapeHtml(m.social || '—') + '</small>' +

            '<small>CNPJ: ' + escapeHtml(formatCnpjDisplay(m.social_revenue)) + '</small>';

        } else {

          text.innerHTML = '<strong>' + escapeHtml(m.fantasia_cliente || m.razao_cliente || 'Cliente') + '</strong>' +

            '<small>Razão social: ' + escapeHtml(m.razao_cliente || '—') + '</small>' +

            '<small>CNPJ: ' + escapeHtml(formatCnpjDisplay(m.cnpj_cliente)) + (m.situacao_cliente ? ' · Situação: ' + escapeHtml(m.situacao_cliente) : '') + '</small>';

        }

        label.appendChild(cb);

        label.appendChild(text);

        container.appendChild(label);

      });

    }



    function fillConsultReview(data) {

      const tf = data.tiflux || {};

      const vh = data.vhsys || {};

      renderConsultMatches(document.getElementById('consultTifluxMatchesBox'), tf.matches_active || [], 'tiflux', 'tiflux_consult_pick');

      renderConsultMatches(document.getElementById('consultVhsysActiveBox'), vh.matches_active || [], 'vhsys', 'vhsys_consult_pick');

      renderConsultMatches(document.getElementById('consultVhsysTrashBox'), vh.matches_trash || [], 'vhsys', 'vhsys_consult_pick');

      document.getElementById('skipTifluxConsultRow').hidden = !tf.found;

      document.getElementById('skipVhsysConsultRow').hidden = !(vh.found);

      document.getElementById('skip_tiflux_consult').checked = false;

      document.getElementById('skip_vhsys_consult').checked = false;

      updateConsultConfirmButton();

    }



    function updateConsultConfirmButton() {

      const btn = document.getElementById('btnConfirmarConsulta');

      const tf = consultPreviewData?.tiflux;

      const vh = consultPreviewData?.vhsys;

      const tfOk = !tf?.found || document.getElementById('skip_tiflux_consult').checked ||

        !!document.querySelector('input[name="tiflux_consult_pick"]:checked');

      const vhOk = !vh?.found || document.getElementById('skip_vhsys_consult').checked ||

        !!document.querySelector('input[name="vhsys_consult_pick"]:checked');

      const anySelected = (tf?.found && !document.getElementById('skip_tiflux_consult').checked) ||

        (vh?.found && !document.getElementById('skip_vhsys_consult').checked);

      btn.disabled = !(tfOk && vhOk && anySelected);

    }



    function formatCnpjDisplay(value) {

      if (!value) return '—';

      const digits = String(value).replace(/\D/g, '');

      if (digits.length !== 14) return String(value);

      return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');

    }



    function formatQueryDisplay(query) {

      if (!query) return '';

      const digits = String(query).replace(/\D/g, '');

      if (digits.length === 14) return formatCnpjDisplay(digits);

      return String(query);

    }



    function formatDateBr(value) {

      if (!value) return '—';

      const s = String(value);

      const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}(?::\d{2})?))?/);

      if (!m) return s;

      return m[3] + '/' + m[2] + '/' + m[1] + (m[4] ? ' às ' + m[4] : '');

    }



    function humanizeKey(key) {

      return String(key).replace(/_cliente$/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

    }



    const TF_LABELS = {

      id: 'Código TiFlux', name: 'Nome fantasia', social: 'Razão social', social_revenue: 'CNPJ',

      status: 'Situação', form_of_payment: 'Forma de pagamento', billing_report_type: 'Tipo de faturamento',

      equipment_counter: 'Equipamentos vinculados', group_counter: 'Grupos vinculados', max_agents: 'Máx. agentes',

      email_financial: 'E-mail financeiro', estadual_registration: 'Inscrição estadual',

      municipal_registration: 'Inscrição municipal', authorization_flow: 'Fluxo de autorização',

    };



    const VH_LABELS = {

      id_cliente: 'Código VHSYS', id_registro: 'Registro interno', razao_cliente: 'Razão social',

      fantasia_cliente: 'Nome fantasia', cnpj_cliente: 'CNPJ', tipo_pessoa: 'Tipo de pessoa',

      tipo_cadastro: 'Tipo de cadastro', situacao_cliente: 'Situação', endereco_cliente: 'Endereço',

      numero_cliente: 'Número', complemento_cliente: 'Complemento', bairro_cliente: 'Bairro',

      cep_cliente: 'CEP', cidade_cliente: 'Cidade', uf_cliente: 'UF', referencia_cliente: 'Referência',

      tel_destinatario_cliente: 'Telefone', doc_destinatario_cliente: 'Documento destinatário',

      email_cliente: 'E-mail', limite_credito: 'Limite de crédito', data_cad_cliente: 'Data de cadastro',

      consumidor_final: 'Consumidor final', modalidade_frete: 'Modalidade de frete',

      ultrapassar_limite_credito: 'Ultrapassar limite de crédito', multiempresa: 'Multiempresa',

      negativado: 'Negativado', negativado_serasa: 'Negativado Serasa',

    };



    const TF_SECTIONS = [

      { title: 'Identificação', keys: ['id', 'name', 'social', 'social_revenue', 'status'] },

      { title: 'Financeiro', keys: ['form_of_payment', 'billing_report_type', 'email_financial'] },

      { title: 'Cadastro fiscal', keys: ['estadual_registration', 'municipal_registration', 'authorization_flow'] },

      { title: 'Resumo de vínculos', keys: ['equipment_counter', 'group_counter', 'max_agents'] },

    ];



    const VH_SECTIONS = [

      { title: 'Identificação', keys: ['id_cliente', 'razao_cliente', 'fantasia_cliente', 'cnpj_cliente', 'tipo_pessoa', 'tipo_cadastro', 'situacao_cliente'] },

      { title: 'Endereço', keys: ['endereco_cliente', 'numero_cliente', 'complemento_cliente', 'bairro_cliente', 'cep_cliente', 'cidade_cliente', 'uf_cliente', 'referencia_cliente'] },

      { title: 'Contato', keys: ['tel_destinatario_cliente', 'email_cliente', 'doc_destinatario_cliente'] },

      { title: 'Financeiro', keys: ['limite_credito', 'ultrapassar_limite_credito', 'consumidor_final', 'modalidade_frete', 'multiempresa'] },

      { title: 'Datas', keys: ['data_cad_cliente'] },

      { title: 'Restrições', keys: ['negativado', 'negativado_serasa'] },

    ];



    const TF_HIDDEN_KEYS = new Set(['desk_ids', 'technical_group_ids', 'address_ids', 'contact_ids', 'logo', 'anotations']);

    const VH_HIDDEN_KEYS = new Set(['lixeira', 'categoria', 'cidade_cliente_cod', 'id_registro']);



    const TF_VALUE_MAPS = {

      form_of_payment: { BOLETO: 'Boleto', CREDIT_CARD: 'Cartão de crédito', PIX: 'PIX' },

      billing_report_type: {

        detailed_with_appointment: 'Detalhado com apontamentos',

        simplified: 'Simplificado',

      },

    };



    function formatDisplayValue(key, val, system) {

      if (val === null || val === undefined || val === '') return '—';

      if (typeof val === 'boolean') {

        if (key === 'status') return val ? 'Ativo' : 'Inativo';

        return val ? 'Sim' : 'Não';

      }

      if (key === 'social_revenue' || key === 'cnpj_cliente') return formatCnpjDisplay(val);

      if (key.startsWith('data_') || key.endsWith('_at')) return formatDateBr(val);

      if (system === 'tiflux' && TF_VALUE_MAPS[key] && TF_VALUE_MAPS[key][val]) return TF_VALUE_MAPS[key][val];

      if (key === 'consumidor_final') return val === '1' || val === 1 ? 'Sim' : 'Não';

      if (key === 'ultrapassar_limite_credito') return val === 1 || val === true ? 'Permitido' : 'Não permitido';

      if (key === 'tipo_pessoa') return val === 'PJ' ? 'Pessoa jurídica' : val === 'PF' ? 'Pessoa física' : String(val);

      if (Array.isArray(val)) {

        if (!val.length) return '—';

        if (val.every((x) => typeof x !== 'object')) return val.join(', ');

        return val.length + ' registro(s)';

      }

      if (typeof val === 'object') return JSON.stringify(val);

      return String(val);

    }



    function buildReportSectionsHtml(obj, sections, labelMap, hiddenKeys, system) {

      let html = '';

      const used = new Set(hiddenKeys);

      sections.forEach((sec) => {

        const rows = sec.keys.filter((k) => Object.prototype.hasOwnProperty.call(obj, k));

        if (!rows.length) return;

        html += '<div class="report-section"><h4>' + escapeHtml(sec.title) + '</h4><dl class="report-dl">';

        rows.forEach((k) => {

          used.add(k);

          const label = labelMap[k] || humanizeKey(k);

          html += '<dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(formatDisplayValue(k, obj[k], system)) + '</dd>';

        });

        html += '</dl></div>';

      });

      const rest = Object.keys(obj).filter((k) => !used.has(k) && obj[k] !== null && obj[k] !== '' &&

        !(Array.isArray(obj[k]) && !obj[k].length) && (typeof obj[k] !== 'object' || Array.isArray(obj[k])));

      if (rest.length) {

        html += '<div class="report-section"><h4>Outros dados</h4><dl class="report-dl">';

        rest.sort().forEach((k) => {

          html += '<dt>' + escapeHtml(labelMap[k] || humanizeKey(k)) + '</dt><dd>' + escapeHtml(formatDisplayValue(k, obj[k], system)) + '</dd>';

        });

        html += '</dl></div>';

      }

      return html;

    }



    function renderListBlock(title, items, labelFn) {

      if (!items || !items.length) return '';

      let html = '<div class="kv-block"><h4>' + escapeHtml(title) + '</h4><ul class="report-list">';

      items.forEach((item) => { html += '<li>' + escapeHtml(labelFn(item)) + '</li>'; });

      html += '</ul></div>';

      return html;

    }



    function renderTifluxEntities(entities) {

      if (!entities || !entities.length) return '';

      let html = '<div class="subsection-label">Campos personalizados</div>';

      entities.forEach((ent) => {

        const fields = (ent.entity_fields || []).filter((f) => f.value !== null && f.value !== undefined && f.value !== '');

        html += '<div class="kv-block"><h4>' + escapeHtml(ent.name || 'Entidade') + '</h4>';

        if (ent.description) html += '<p class="hint">' + escapeHtml(ent.description) + '</p>';

        if (!fields.length) {

          html += '<p class="hint">Nenhum campo preenchido.</p>';

        } else {

          html += '<dl class="report-dl">';

          fields.forEach((f) => {

            html += '<dt>' + escapeHtml(f.name || 'Campo') + '</dt><dd>' + escapeHtml(formatDisplayValue('entity', f.value, 'tiflux')) + '</dd>';

          });

          html += '</dl>';

        }

        html += '</div>';

      });

      return html;

    }



    function renderConsultReport(data) {

      consultDetailData = data;

      document.getElementById('consultReportQuery').textContent = 'Consulta: ' + formatQueryDisplay(data.query || '');

      const grid = document.getElementById('consultReportGrid');

      grid.innerHTML = '';

      const tf = data.tiflux || {};

      const vh = data.vhsys || {};

      const tfCol = document.createElement('div');

      tfCol.className = 'consult-col';

      if (tf.skipped) {

        tfCol.innerHTML = '<h3>TiFlux</h3><p class="hint">Não consultado.</p>';

      } else if (!tf.success) {

        tfCol.innerHTML = '<h3>TiFlux</h3><p class="err">' + escapeHtml(tf.error || 'Falha ao carregar') + '</p>';

      } else {

        const profile = tf.data || {};

        const client = profile.client || {};

        const entities = profile.entities || (client.entities || []);

        let html = '<h3>TiFlux</h3>';

        html += renderListBlock('Mesas de serviço', profile.desks, (d) =>

          (d.display_name || d.name || 'Mesa') + (d.active === false ? ' (inativa)' : ''));

        html += renderListBlock('Grupos de atendentes', profile.technical_groups, (g) => g.name || 'Grupo');

        html += '<div class="subsection-label">Dados do cadastro</div>';

        html += buildReportSectionsHtml(client, TF_SECTIONS, TF_LABELS, TF_HIDDEN_KEYS, 'tiflux');

        html += renderTifluxEntities(entities);

        tfCol.innerHTML = html;

      }

      grid.appendChild(tfCol);

      const vhCol = document.createElement('div');

      vhCol.className = 'consult-col';

      if (vh.skipped) {

        vhCol.innerHTML = '<h3>VHSYS</h3><p class="hint">Não consultado.</p>';

      } else if (!vh.success) {

        vhCol.innerHTML = '<h3>VHSYS</h3><p class="err">' + escapeHtml(vh.error || 'Falha ao carregar') + '</p>';

      } else {

        const client = vh.data || {};

        let html = '<h3>VHSYS</h3>';

        const cat = client.categoria || client.nome_categoria;

        if ((Array.isArray(cat) ? cat.length : cat) || client.id_categoria) {

          const catText = Array.isArray(cat) ? (cat.length ? cat.join(', ') : '—') : String(cat || '—');

          html += '<div class="kv-block"><h4>Categoria</h4><p>' + escapeHtml(catText) + '</p></div>';

        }

        html += '<div class="subsection-label">Dados do cadastro</div>';

        html += buildReportSectionsHtml(client, VH_SECTIONS, VH_LABELS, VH_HIDDEN_KEYS, 'vhsys');

        vhCol.innerHTML = html;

      }

      grid.appendChild(vhCol);

    }



    document.getElementById('menuConsulta').addEventListener('click', () => {

      consultPreviewData = null;

      consultDetailData = null;

      document.getElementById('formConsultSearch').reset();

      document.getElementById('alertConsultSearch').hidden = true;

      document.getElementById('alertConsultReview').hidden = true;

      showConsultFlow(1);

    });

    document.getElementById('menuConsulta').addEventListener('keydown', (e) => {

      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('menuConsulta').click(); }

    });

    document.getElementById('btnCancelarConsulta').addEventListener('click', showHome);

    document.getElementById('btnInicioConsulta').addEventListener('click', showHome);

    document.getElementById('btnVoltarConsulta').addEventListener('click', () => showConsultFlow(1));

    document.getElementById('btnNovaConsulta').addEventListener('click', () => {

      consultPreviewData = null;

      consultDetailData = null;

      document.getElementById('formConsultSearch').reset();

      showConsultFlow(1);

    });

    document.getElementById('btnImprimirConsulta').addEventListener('click', () => window.print());

    document.getElementById('btnBaixarJsonConsulta').addEventListener('click', () => {

      if (!consultDetailData) return;

      const blob = new Blob([JSON.stringify(consultDetailData, null, 2)], { type: 'application/json' });

      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');

      const slug = (consultDetailData.query || 'consulta').replace(/\\W+/g, '_').slice(0, 40);

      a.href = url;

      a.download = 'consulta-' + slug + '-' + Date.now() + '.json';

      a.click();

      URL.revokeObjectURL(url);

    });

    ['skip_tiflux_consult', 'skip_vhsys_consult'].forEach((id) => {

      document.getElementById(id).addEventListener('change', updateConsultConfirmButton);

    });

    document.getElementById('consultTifluxMatchesBox').addEventListener('change', updateConsultConfirmButton);

    document.getElementById('consultVhsysActiveBox').addEventListener('change', updateConsultConfirmButton);

    document.getElementById('consultVhsysTrashBox').addEventListener('change', updateConsultConfirmButton);

    document.getElementById('formConsultSearch').addEventListener('submit', async (e) => {

      e.preventDefault();

      document.getElementById('alertConsultSearch').hidden = true;

      const btn = document.getElementById('btnBuscarConsulta');

      const query = document.getElementById('consult_query').value.trim();

      btn.disabled = true;

      btn.textContent = 'Buscando...';

      try {

        const res = await fetch('/consulta/preview', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ query }),

        });

        let data;

        try { data = await res.json(); } catch { data = { error: 'Resposta inválida.' }; }

        if (!res.ok || data.success === false) {

          showAlert('alertConsultSearch', 'alertConsultSearchText', data.error || 'Busca falhou.');

          return;

        }

        if (!data.tiflux?.found && !data.vhsys?.found) {

          showAlert('alertConsultSearch', 'alertConsultSearchText', ' Nenhum cliente encontrado em TiFlux ou VHSYS.');

          return;

        }

        consultPreviewData = data;

        consultPreviewData._rawQuery = query;

        fillConsultReview(data);

        showConsultFlow(2);

      } finally {

        btn.disabled = false;

        btn.textContent = 'Buscar';

      }

    });

    document.getElementById('btnConfirmarConsulta').addEventListener('click', async () => {

      document.getElementById('alertConsultReview').hidden = true;

      if (!consultPreviewData) return;

      const btn = document.getElementById('btnConfirmarConsulta');

      const tf = consultPreviewData.tiflux || {};

      const vh = consultPreviewData.vhsys || {};

      let tifluxId = null;

      let vhsysId = null;

      if (tf.found && !document.getElementById('skip_tiflux_consult').checked) {

        const picked = document.querySelector('input[name="tiflux_consult_pick"]:checked');

        if (!picked) {

          showAlert('alertConsultReview', 'alertConsultReviewText', ' Selecione um cliente no TiFlux.');

          return;

        }

        tifluxId = Number(picked.value);

      }

      if (vh.found && !document.getElementById('skip_vhsys_consult').checked) {

        const picked = document.querySelector('input[name="vhsys_consult_pick"]:checked');

        if (!picked) {

          showAlert('alertConsultReview', 'alertConsultReviewText', ' Selecione um cliente no VHSYS.');

          return;

        }

        vhsysId = Number(picked.value);

      }

      if (tifluxId === null && vhsysId === null) {

        showAlert('alertConsultReview', 'alertConsultReviewText', ' Selecione ao menos um sistema.');

        return;

      }

      btn.disabled = true;

      btn.textContent = 'Carregando...';

      try {

        const res = await fetch('/consulta/detalhe', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            query: consultPreviewData._rawQuery || consultPreviewData.query,

            tiflux_client_id: tifluxId,

            vhsys_client_id: vhsysId,

          }),

        });

        let data;

        try { data = await res.json(); } catch { data = { error: 'Resposta inválida.' }; }

        if (!res.ok && !data.tiflux && !data.vhsys) {

          showAlert('alertConsultReview', 'alertConsultReviewText', data.error || 'Falha ao carregar relatório.');

          return;

        }

        renderConsultReport(data);

        showConsultFlow(3);

      } finally {

        btn.disabled = false;

        btn.textContent = 'Carregar relatório';

        updateConsultConfirmButton();

      }

    });

  </script>

</body>

</html>"""


