INDEX_HTML = """<!DOCTYPE html>

<html lang="pt-BR">

<head>

  <meta charset="utf-8">

  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>AVS Integrações</title>

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

          <div class="menu-item disabled">

            <div class="menu-icon" style="background:#94a3b8;">…</div>

            <h3>Em breve</h3>

            <p>Novas integrações serão disponibilizadas neste menu.</p>

          </div>

        </div>

      </div>

      <p class="footer-note">AVS Tecnologia · Integração interna</p>

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

  </main>



  <script>

    let previewData = null;



    const panelHome = document.getElementById('panelHome');

    const panelFlow = document.getElementById('panelFlow');

    const btnHomeTop = document.getElementById('btnHomeTop');

    const subPanels = [document.getElementById('subPanel1'), document.getElementById('subPanel2'), document.getElementById('subPanel3')];

    const stepEls = document.querySelectorAll('#stepsBar .step');



    function showHome() {

      panelHome.classList.add('active');

      panelFlow.classList.remove('active');

      btnHomeTop.hidden = true;

    }



    function showFlow(step) {

      panelHome.classList.remove('active');

      panelFlow.classList.add('active');

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

  </script>

</body>

</html>"""


