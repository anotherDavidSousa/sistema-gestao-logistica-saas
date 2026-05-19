/**
 * admin_extra.js — Fertran Filial 16
 * Carregado em todas as páginas do admin via JAZZMIN_SETTINGS["custom_js"].
 *
 * Funcionalidades:
 *   1. Toggle dark / light mode (sun/moon no topbar, persiste em localStorage)
 *   2. Busca global no topbar (barra de pesquisa + dropdown de resultados)
 *   3. Botões "+" quick-add na sidebar (ao lado de cada model com permissão de adição)
 *   4. Oculta o control-sidebar button (painel lateral desnecessário do AdminLTE)
 */
(function () {
  'use strict';

  /* ════════════════════════════════════════════════════════════════════════
     1. DARK / LIGHT MODE TOGGLE
     ════════════════════════════════════════════════════════════════════════ */

  const DARK_KEY = 'f16_dark_mode';

  // Jazzmin >= 3 / Bootstrap 5: dark mode via data-bs-theme no <html>
  function isDark() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
  }

  function applyTheme(dark) {
    document.documentElement.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
    updateToggleIcon();
    localStorage.setItem(DARK_KEY, dark ? '1' : '0');
  }

  function updateToggleIcon() {
    const btn = document.getElementById('f16-theme-toggle');
    if (!btn) return;
    if (isDark()) {
      btn.innerHTML = '<i class="fas fa-sun" style="color:#fbbf24"></i>';
      btn.title = 'Modo claro';
    } else {
      btn.innerHTML = '<i class="fas fa-moon" style="color:#64748b"></i>';
      btn.title = 'Modo escuro';
    }
  }

  function injectThemeToggle() {
    if (document.getElementById('f16-theme-toggle')) return;

    // Procura o nav-item de usuário (fica à direita do topbar)
    const userMenu = document.querySelector('.main-header .navbar-nav.ml-auto') ||
                     document.querySelector('.main-header .navbar-nav');
    if (!userMenu) return;

    const li = document.createElement('li');
    li.className = 'nav-item';
    li.style.cssText = 'display:flex;align-items:center;';

    const btn = document.createElement('button');
    btn.id = 'f16-theme-toggle';
    btn.type = 'button';
    btn.style.cssText = `
      background: none;
      border: 1px solid var(--f16-border, #e5e7eb);
      border-radius: 8px;
      padding: 5px 9px;
      cursor: pointer;
      font-size: 14px;
      line-height: 1;
      transition: background .15s, border-color .15s;
      margin: 0 4px;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
    btn.addEventListener('mouseover', () => {
      btn.style.background = isDark() ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.05)';
      btn.style.borderColor = '#3b82f6';
    });
    btn.addEventListener('mouseout', () => {
      btn.style.background = 'none';
      btn.style.borderColor = '';
    });
    btn.addEventListener('click', () => applyTheme(!isDark()));

    li.appendChild(btn);

    // Insere antes do primeiro item do nav direito
    userMenu.insertBefore(li, userMenu.firstChild);
    updateToggleIcon();
  }

  // Aplica o tema salvo ANTES do paint (evita flash claro → escuro)
  (function applyStoredTheme() {
    const stored = localStorage.getItem(DARK_KEY);
    // Padrão: light. Só muda se o usuário explicitamente escolheu dark.
    document.documentElement.setAttribute('data-bs-theme', stored === '1' ? 'dark' : 'light');
  })();


  /* ════════════════════════════════════════════════════════════════════════
     2. OCULTAR CONTROL-SIDEBAR (painel de settings lateral do AdminLTE)
     ════════════════════════════════════════════════════════════════════════ */

  function hideControlSidebar() {
    // Botão do control-sidebar no topbar
    const btns = document.querySelectorAll(
      '[data-widget="control-sidebar"], .nav-link[data-widget="control-sidebar"]'
    );
    btns.forEach(el => {
      const li = el.closest('li.nav-item') || el.closest('li') || el;
      li.style.display = 'none';
    });
    // O painel lateral em si
    const panel = document.querySelector('.control-sidebar, aside.control-sidebar');
    if (panel) panel.style.display = 'none';
  }


  /* ════════════════════════════════════════════════════════════════════════
     3. BUSCA GLOBAL
     ════════════════════════════════════════════════════════════════════════ */

  const SEARCH_URL = '/admin/global-search/';

  const TYPE_ICON = {
    'Cavalo':      'fa-truck',
    'Carreta':     'fa-trailer',
    'Motorista':   'fa-id-card',
    'Proprietário':'fa-building',
    'OST':         'fa-file-invoice',
    'CT-e':        'fa-file-contract',
  };
  const TYPE_COLOR = {
    'Cavalo':      '#3b82f6',
    'Carreta':     '#8b5cf6',
    'Motorista':   '#059669',
    'Proprietário':'#d97706',
    'OST':         '#0891b2',
    'CT-e':        '#dc2626',
  };

  function injectSearchBar() {
    if (document.getElementById('f16-search-wrap')) return;

    const navbar = document.querySelector('.main-header .navbar-nav.mr-auto') ||
                   document.querySelector('.main-header .navbar');
    if (!navbar) return;

    const wrap = document.createElement('div');
    wrap.id = 'f16-search-wrap';
    wrap.style.cssText = `
      position: relative;
      display: flex;
      align-items: center;
      margin: 0 8px;
      flex: 1;
      max-width: 340px;
    `;
    wrap.innerHTML = `
      <i class="fas fa-search" style="
        position:absolute;left:11px;top:50%;transform:translateY(-50%);
        color:#9ca3af;font-size:12px;pointer-events:none;z-index:1;
      "></i>
      <input
        id="f16-search-input"
        type="text"
        placeholder="Buscar placa, motorista, OST…"
        autocomplete="off"
        style="
          width:100%;
          padding:6px 12px 6px 30px;
          border:1px solid var(--f16-border,#e5e7eb);
          border-radius:8px;
          font-size:12.5px;
          background:var(--f16-bg,#f0f2f5);
          color:var(--f16-text,#111827);
          outline:none;
          transition:border-color .15s,background .15s;
        "
      >
      <div id="f16-search-dropdown" style="
        display:none;
        position:absolute;
        top:calc(100% + 6px);
        left:0;right:0;
        background:var(--f16-card,#fff);
        border:1px solid var(--f16-border,#e5e7eb);
        border-radius:10px;
        box-shadow:0 8px 24px rgba(0,0,0,.13);
        z-index:9999;
        overflow:hidden;
        max-height:380px;
        overflow-y:auto;
      "></div>
    `;

    // Insere após os links de topo
    const topmenu = document.querySelector('.main-header .navbar-nav.mr-auto');
    if (topmenu) {
      topmenu.parentNode.insertBefore(wrap, topmenu.nextSibling);
    } else {
      navbar.appendChild(wrap);
    }

    const input    = document.getElementById('f16-search-input');
    const dropdown = document.getElementById('f16-search-dropdown');
    let searchTimer = null;

    input.addEventListener('focus', () => {
      input.style.borderColor = '#3b82f6';
      input.style.background  = 'var(--f16-card,#fff)';
      if (input.value.trim().length >= 2) dropdown.style.display = 'block';
    });
    input.addEventListener('blur', () => {
      input.style.borderColor = '';
      input.style.background  = '';
      setTimeout(() => { dropdown.style.display = 'none'; }, 200);
    });
    input.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const q = input.value.trim();
      if (q.length < 2) { dropdown.style.display = 'none'; return; }
      dropdown.style.display = 'block';
      dropdown.innerHTML = `<div style="padding:12px 14px;font-size:12px;color:#9ca3af;display:flex;align-items:center;gap:8px">
        <span style="width:14px;height:14px;border:2px solid #e5e7eb;border-top-color:#3b82f6;
          border-radius:50%;animation:f16-spin .7s linear infinite;display:inline-block"></span>
        Buscando…</div>`;
      searchTimer = setTimeout(() => doSearch(q), 280);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') { dropdown.style.display = 'none'; input.blur(); }
    });
  }

  async function doSearch(q) {
    const dropdown = document.getElementById('f16-search-dropdown');
    if (!dropdown) return;
    try {
      const resp = await fetch(`${SEARCH_URL}?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
      const data = await resp.json();
      renderResults(data.results, q);
    } catch {
      dropdown.innerHTML = `<div style="padding:12px 14px;font-size:12px;color:#dc2626">Erro na busca</div>`;
    }
  }

  function renderResults(results, q) {
    const dropdown = document.getElementById('f16-search-dropdown');
    if (!dropdown) return;
    if (!results.length) {
      dropdown.innerHTML = `<div style="padding:16px;font-size:12.5px;color:#9ca3af;text-align:center">
        <i class="fas fa-search-minus" style="margin-right:6px"></i>
        Nenhum resultado para "<b style="color:#374151">${esc(q)}</b>"</div>`;
      return;
    }
    const groups = {};
    results.forEach(r => { if (!groups[r.tipo]) groups[r.tipo] = []; groups[r.tipo].push(r); });
    let html = '';
    for (const tipo in groups) {
      const icon  = TYPE_ICON[tipo]  || 'fa-circle';
      const color = TYPE_COLOR[tipo] || '#6b7280';
      html += `<div style="padding:5px 14px 2px;font-size:10px;font-weight:700;text-transform:uppercase;
        letter-spacing:.07em;color:${color};border-top:1px solid var(--f16-border,#f3f4f6)">${esc(tipo)}</div>`;
      groups[tipo].forEach(r => {
        html += `<a href="${r.url}" style="display:flex;align-items:center;gap:10px;padding:8px 14px;
          text-decoration:none;transition:background .1s"
          onmouseover="this.style.background='var(--f16-bg,#f8fafc)'"
          onmouseout="this.style.background=''">
          <span style="width:28px;height:28px;border-radius:7px;background:${color}18;color:${color};
            display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0">
            <i class="fas ${icon}"></i></span>
          <span style="flex:1;min-width:0">
            <span style="display:block;font-size:12.5px;font-weight:600;color:var(--f16-text,#111827);
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
              ${highlight(esc(r.label), q)}</span>
            ${r.sub ? `<span style="font-size:11px;color:#9ca3af;display:block;white-space:nowrap;
              overflow:hidden;text-overflow:ellipsis">${esc(r.sub)}</span>` : ''}
          </span>
          <i class="fas fa-arrow-right" style="font-size:9px;color:#d1d5db;flex-shrink:0"></i>
        </a>`;
      });
    }
    dropdown.innerHTML = html;
  }

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function highlight(text, q) {
    const re = new RegExp(`(${esc(q).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`, 'gi');
    return text.replace(re, '<mark style="background:#fef9c3;color:#92400e;border-radius:2px;padding:0 1px">$1</mark>');
  }


  /* ════════════════════════════════════════════════════════════════════════
     4. BOTÕES "+" QUICK-ADD NA SIDEBAR
     ════════════════════════════════════════════════════════════════════════ */

  const QUICK_ADD_MAP = {
    'Cavalos':       '/admin/core/cavalo/add/',
    'Carretas':      '/admin/core/carreta/add/',
    'Motoristas':    '/admin/core/motorista/add/',
    'Proprietários': '/admin/core/proprietario/add/',
    'Gestores':      '/admin/core/gestor/add/',
    'OSTs':          '/admin/fila/ost/add/',
    'CT-es':         '/admin/fila/cte/add/',
  };

  function injectSidebarButtons() {
    document.querySelectorAll('.nav-sidebar .nav-item').forEach(item => {
      const link = item.querySelector(':scope > .nav-link');
      if (!link || item.querySelector('.f16-add-btn')) return;
      const text = link.textContent.trim();
      const addUrl = QUICK_ADD_MAP[text];
      if (!addUrl) return;

      const btn = document.createElement('a');
      btn.href = addUrl;
      btn.className = 'f16-add-btn';
      btn.title = `Adicionar ${text.replace(/s$/, '')}`;
      btn.style.cssText = `
        display:flex;align-items:center;justify-content:center;
        width:20px;height:20px;border-radius:5px;
        background:rgba(59,130,246,.15);color:#3b82f6;
        font-size:11px;margin-left:auto;margin-right:8px;
        text-decoration:none;flex-shrink:0;transition:background .15s;
      `;
      btn.innerHTML = '<i class="fas fa-plus"></i>';
      btn.addEventListener('mouseover', () => { btn.style.background = 'rgba(59,130,246,.3)'; });
      btn.addEventListener('mouseout',  () => { btn.style.background = 'rgba(59,130,246,.15)'; });
      btn.addEventListener('click', e => e.stopPropagation());

      link.style.display = 'flex';
      link.style.alignItems = 'center';
      link.appendChild(btn);
    });
  }


  /* ════════════════════════════════════════════════════════════════════════
     INICIALIZAÇÃO
     ════════════════════════════════════════════════════════════════════════ */

  function init() {
    hideControlSidebar();
    injectThemeToggle();
    injectSearchBar();
    injectSidebarButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Retry após Jazzmin terminar de montar a sidebar (pode usar JS próprio)
  setTimeout(init, 600);
  setTimeout(hideControlSidebar, 1200); // segundo pass para garantir

})();
