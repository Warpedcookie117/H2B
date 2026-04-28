/* promociones.js — Lógica de la página de paquetes y regalos */

(function () {
  'use strict';

  const cfg  = window.PROM_CONFIG || {};
  const URLS = cfg.urls || {};

  // ── Helpers ────────────────────────────────────────────────────
  function csrf() {
    return document.cookie.split('; ')
      .find(r => r.startsWith('csrftoken='))?.split('=')[1] || '';
  }

  function showMsg(tipo, texto) {
    const id = tipo === 'ok' ? 'msgSuccess' : 'msgError';
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = texto;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 3500);
  }

  // ── Accordion trigger sync ────────────────────────────────────
  const DOT_COLORS = {
    paquete: {
      todos:           '#d1d5db',
      categoria:       '#CCFF00',
      monto:           '#FFD6A5',
      monto_categoria: '#00F5D4',
    },
    oferta: {
      todos:      '#d1d5db',
      porcentaje: '#FF006E',
      fijo:       '#8338EC',
      '2x1':      '#FFD6A5',
      nxprecio:   '#00F5D4',
    },
  };

  function _syncTrigger(navId, tipo, seccion) {
    const nav = document.getElementById(navId);
    if (!nav) return;
    nav.classList.remove('open');
    const trigger = nav.querySelector('.prom-tabs__trigger');
    if (!trigger) return;
    const activeTab = nav.querySelector(`.prom-tab[data-tipo="${tipo}"]`);
    const label = activeTab?.querySelector('.prom-tab__label')?.textContent || tipo;
    trigger.querySelector('.prom-tabs__trigger-label').textContent = label;
    const dot = trigger.querySelector('.prom-tabs__trigger-dot');
    if (dot) dot.style.background = (DOT_COLORS[seccion] || {})[tipo] || '#d1d5db';
  }

  // ── Filtrado ───────────────────────────────────────────────────
  const TITULOS = {
    todos:           'Todos los paquetes y regalos',
    categoria:       'Paquetes',
    monto:           'Regalos por compra grande',
    monto_categoria: 'Regalos por categoría',
  };

  function actualizarConteos() {
    const cards  = document.querySelectorAll('#promCards .prom-card');
    const counts = { todos: 0, categoria: 0, monto: 0, monto_categoria: 0 };
    cards.forEach(c => { counts.todos++; if (c.dataset.tipo in counts) counts[c.dataset.tipo]++; });
    document.querySelectorAll('.prom-tab[data-seccion="paquete"]').forEach(tab => {
      const el = tab.querySelector('.prom-tab__count');
      if (el) el.textContent = counts[tab.dataset.tipo] ?? 0;
    });
  }

  function filtrar(tipo, animate = true) {
    document.querySelectorAll('.prom-tab[data-seccion="paquete"]')
      .forEach(b => b.classList.toggle('activo', b.dataset.tipo === tipo));
    _syncTrigger('tabsPaquetes', tipo, 'paquete');

    const wrap = document.getElementById('promCards');
    if (!wrap) return;

    const aplicar = () => {
      let visible = 0;
      wrap.querySelectorAll('.prom-card').forEach(card => {
        const match = tipo === 'todos' || card.dataset.tipo === tipo;
        card.classList.toggle('oculta', !match);
        if (match) visible++;
      });
      const empty = document.getElementById('promEmpty');
      if (empty) empty.classList.toggle('hidden', visible > 0);
      const titulo = document.getElementById('promTitulo');
      if (titulo) titulo.textContent = TITULOS[tipo] || 'Paquetes y Regalos';
    };

    if (!animate) { aplicar(); return; }

    wrap.style.transition = 'opacity .15s ease, transform .15s ease';
    wrap.style.opacity    = '0';
    wrap.style.transform  = 'translateY(4px)';
    setTimeout(() => {
      aplicar();
      wrap.style.opacity   = '1';
      wrap.style.transform = 'translateY(0)';
    }, 160);
  }

  // ── Filtrado de OFERTAS ────────────────────────────────────────
  const TITULOS_OFERTA = {
    todos:      'Todas las ofertas y descuentos',
    porcentaje: 'Descuentos por porcentaje',
    fijo:       'Descuentos en pesos',
    '2x1':      'Ofertas 2×1',
    nxprecio:   'Precios de paquete',
  };

  function actualizarConteosOfertas() {
    const cards  = document.querySelectorAll('#ofertaCards .prom-card');
    const counts = { todos: 0, porcentaje: 0, fijo: 0, '2x1': 0, nxprecio: 0 };
    cards.forEach(c => { counts.todos++; if (c.dataset.tipo in counts) counts[c.dataset.tipo]++; });
    document.querySelectorAll('.prom-tab[data-seccion="oferta"]').forEach(tab => {
      const el = tab.querySelector('.prom-tab__count');
      if (el) el.textContent = counts[tab.dataset.tipo] ?? 0;
    });
  }

  function filtrarOfertas(tipo, animate = true) {
    document.querySelectorAll('.prom-tab[data-seccion="oferta"]')
      .forEach(b => b.classList.toggle('activo', b.dataset.tipo === tipo));
    _syncTrigger('tabsOfertas', tipo, 'oferta');

    const wrap = document.getElementById('ofertaCards');
    if (!wrap) return;

    const aplicar = () => {
      let visible = 0;
      wrap.querySelectorAll('.prom-card').forEach(card => {
        const match = tipo === 'todos' || card.dataset.tipo === tipo;
        card.classList.toggle('oculta', !match);
        if (match) visible++;
      });
      const empty = document.getElementById('ofertaEmpty');
      if (empty) empty.classList.toggle('hidden', visible > 0);
      const titulo = document.getElementById('ofertaTitulo');
      if (titulo) titulo.textContent = TITULOS_OFERTA[tipo] || 'Ofertas y Descuentos';
    };

    if (!animate) { aplicar(); return; }

    wrap.style.transition = 'opacity .15s ease, transform .15s ease';
    wrap.style.opacity    = '0';
    wrap.style.transform  = 'translateY(4px)';
    setTimeout(() => {
      aplicar();
      wrap.style.opacity   = '1';
      wrap.style.transform = 'translateY(0)';
    }, 160);
  }

  // ── Modo toggle (Paquetes / Ofertas) ──────────────────────────
  function setModo(modo) {
    document.querySelectorAll('.prom-modo__btn').forEach(b =>
      b.classList.toggle('activo', b.dataset.modo === modo)
    );
    const secPaq = document.getElementById('seccionPaquetes');
    const secOfe = document.getElementById('seccionOfertas');
    if (secPaq) secPaq.style.display = modo === 'paquetes' ? '' : 'none';
    if (secOfe) secOfe.style.display = modo === 'ofertas'  ? '' : 'none';
  }

  // ── Modal principal ────────────────────────────────────────────
  function abrirModal(tipo = 'promo') {
    const box = document.querySelector('#modalPromocion .prom-modal__box');
    if (box) {
      box.classList.remove('prom-modal__box--promo', 'prom-modal__box--oferta');
      box.classList.add('prom-modal__box--' + tipo);
    }
    document.getElementById('modalPromocion').classList.add('open');
  }
  function cerrarModal() {
    document.getElementById('modalPromocion').classList.remove('open');
  }

  async function nuevaPromo() {
    abrirModal('promo');
    document.getElementById('modalContenido').innerHTML =
      '<p style="padding:2rem;font-weight:600;color:#9ca3af;">Cargando…</p>';
    const res  = await fetch(URLS.modalNueva);
    const data = await res.json();
    document.getElementById('modalContenido').innerHTML = data.html;
    initFormLogic();
  }

  async function editarPromo(id) {
    abrirModal('promo');
    document.getElementById('modalContenido').innerHTML =
      '<p style="padding:2rem;font-weight:600;color:#9ca3af;">Cargando…</p>';
    const res  = await fetch(URLS.modalEditar + id + '/');
    const data = await res.json();
    document.getElementById('modalContenido').innerHTML = data.html;
    initFormLogic();
  }

  async function enviarPromocion(event, promocionId) {
    event.preventDefault();
    const form = event.target;
    const url  = promocionId ? URLS.guardar + promocionId + '/' : URLS.guardarNueva;
    const res  = await fetch(url, { method: 'POST', body: new FormData(form) });
    const data = await res.json();
    if (data.ok) {
      cerrarModal();
      showMsg('ok', data.msg);
      setTimeout(() => location.reload(), 800);
    } else {
      const errEl = document.getElementById('formError');
      if (errEl) { errEl.textContent = data.msg; errEl.classList.remove('hidden'); }
    }
  }

  // ── CRUD Ofertas ───────────────────────────────────────────────
  async function nuevaOferta() {
    abrirModal('oferta');
    document.getElementById('modalContenido').innerHTML =
      '<p style="padding:2rem;font-weight:600;color:#9ca3af;">Cargando…</p>';
    const res  = await fetch(URLS.modalNuevaOferta);
    const data = await res.json();
    document.getElementById('modalContenido').innerHTML = data.html;
    initOfertaFormLogic();
  }

  async function editarOferta(id) {
    abrirModal('oferta');
    document.getElementById('modalContenido').innerHTML =
      '<p style="padding:2rem;font-weight:600;color:#9ca3af;">Cargando…</p>';
    const res  = await fetch(URLS.modalEditarOferta + id + '/');
    const data = await res.json();
    document.getElementById('modalContenido').innerHTML = data.html;
    initOfertaFormLogic();
  }

  async function enviarOferta(event, ofertaId) {
    event.preventDefault();
    const form = event.target;
    const url  = ofertaId ? URLS.guardarOferta + ofertaId + '/' : URLS.guardarNuevaOferta;
    const res  = await fetch(url, { method: 'POST', body: new FormData(form) });
    const data = await res.json();
    if (data.ok) {
      cerrarModal();
      showMsg('ok', data.msg);
      setTimeout(() => location.reload(), 800);
    } else {
      const errEl = document.getElementById('ofertaFormError');
      if (errEl) { errEl.textContent = data.msg; errEl.classList.remove('hidden'); }
    }
  }

  async function toggleOferta(id) {
    const res  = await fetch(URLS.toggleOferta + id + '/', {
      method: 'POST', headers: { 'X-CSRFToken': csrf() },
    });
    const data = await res.json();
    if (data.ok) {
      showMsg('ok', data.activo ? 'Oferta activada.' : 'Oferta pausada.');
      setTimeout(() => location.reload(), 600);
    }
  }

  // ── Toggle activo/inactivo ─────────────────────────────────────
  async function togglePromo(id) {
    const res  = await fetch(URLS.toggle + id + '/', {
      method: 'POST', headers: { 'X-CSRFToken': csrf() },
    });
    const data = await res.json();
    if (data.ok) {
      showMsg('ok', data.activo ? 'Activada.' : 'Pausada.');
      setTimeout(() => location.reload(), 600);
    }
  }

  // ── Eliminar ───────────────────────────────────────────────────
  let _pendingDeleteId   = null;
  let _pendingDeleteTipo = 'promo'; // 'promo' | 'oferta'

  function confirmarEliminar(id, nombre, tipo = 'promo') {
    _pendingDeleteId   = id;
    _pendingDeleteTipo = tipo;
    const el = document.getElementById('confirmNombre');
    if (el) el.textContent = nombre;
    document.getElementById('modalConfirmar').classList.add('open');
  }

  function cerrarConfirmar() {
    _pendingDeleteId   = null;
    _pendingDeleteTipo = 'promo';
    document.getElementById('modalConfirmar').classList.remove('open');
  }

  async function ejecutarEliminar() {
    if (!_pendingDeleteId) return;
    const url = _pendingDeleteTipo === 'oferta'
      ? URLS.eliminarOferta + _pendingDeleteId + '/'
      : URLS.eliminar       + _pendingDeleteId + '/';
    const res  = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    const data = await res.json();
    cerrarConfirmar();
    if (data.ok) {
      showMsg('ok', data.msg);
      setTimeout(() => location.reload(), 600);
    }
  }

  // ── Utilidad compartida: gestor de filas de atributos ─────────
  //
  // Parámetros:
  //   rowsContainer  — elemento <div> que contiene las filas
  //   addBtn         — botón "+ Agregar filtro"
  //   getCatId       — función () => id de la categoría seleccionada
  //   nombreClass    — clase CSS del <select> nombre de cada fila
  //   valorClass     — clase CSS del <select> valor de cada fila
  //
  function crearGestorFiltros(rowsContainer, addBtn, getCatId, nombreClass, valorClass) {
    if (!rowsContainer) return { cargarAtributos: () => {} };
    let atributosData = [];

    // Deshabilita en cada select de nombre las opciones ya elegidas en otras filas
    function _actualizarDuplicados() {
      const selects = Array.from(rowsContainer.querySelectorAll('.' + nombreClass));
      const usados  = new Set(selects.map(s => s.value).filter(Boolean));
      selects.forEach(s => {
        Array.from(s.options).forEach(opt => {
          if (!opt.value) return;
          opt.disabled = opt.value !== s.value && usados.has(opt.value);
        });
      });
    }

    function _poblarValor(sel, nombreAtrib, preValor = '') {
      if (!sel) return;
      const prev  = preValor || sel.dataset.preValor || sel.value || '';
      const found = atributosData.find(a => a.nombre === nombreAtrib);
      sel.innerHTML = '<option value="">— Valor —</option>';
      (found?.valores || []).forEach(v => {
        const opt = document.createElement('option');
        opt.value = v; opt.textContent = v;
        if (v === prev) opt.selected = true;
        sel.appendChild(opt);
      });
      if (sel.dataset.preValor) sel.dataset.preValor = '';
    }

    function _poblarNombre(sel, preNombre = '') {
      const prevNombre = sel.value || preNombre;
      const fila       = sel.closest('.filtro-fila');
      const valSel     = fila?.querySelector('.' + valorClass);
      const prevValor  = valSel?.dataset.preValor || valSel?.value || '';

      sel.innerHTML = '<option value="">— Atributo —</option>';
      atributosData.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.nombre; opt.textContent = a.nombre;
        if (a.nombre === prevNombre) opt.selected = true;
        sel.appendChild(opt);
      });

      _poblarValor(valSel, sel.value, prevValor);
      _actualizarDuplicados();
    }

    function _repoblarTodosNombre() {
      rowsContainer.querySelectorAll('.' + nombreClass).forEach(sel => {
        const preNombre = sel.dataset.preNombre || '';
        _poblarNombre(sel, preNombre);
        if (preNombre) sel.dataset.preNombre = '';
      });
    }

    async function cargarAtributos() {
      const catId = getCatId();
      atributosData = [];
      if (!catId) { _repoblarTodosNombre(); return; }
      const res  = await fetch(`/ventas/promociones/atributos-categoria/${catId}/`);
      const data = await res.json();
      atributosData = data.atributos || [];
      _repoblarTodosNombre();
    }

    function _bindFila(fila) {
      const nomSel = fila.querySelector('.' + nombreClass);
      const valSel = fila.querySelector('.' + valorClass);
      nomSel?.addEventListener('change', () => {
        _poblarValor(valSel, nomSel.value);
        _actualizarDuplicados();
      });
    }

    function agregarFila() {
      const fila = document.createElement('div');
      fila.className = 'filtro-fila flex gap-2 items-center';
      fila.innerHTML = `
        <div class="flex-1">
          <select name="filtro_nombre[]"
                  class="${nombreClass} w-full border-2 border-black px-2 py-1 font-semibold text-sm outline-none bg-white">
            <option value="">— Atributo —</option>
          </select>
        </div>
        <div class="flex-1">
          <select name="filtro_valor[]"
                  class="${valorClass} w-full border-2 border-black px-2 py-1 font-semibold text-sm outline-none bg-white">
            <option value="">— Valor —</option>
          </select>
        </div>
        <button type="button"
                class="border-2 border-black px-2 py-1 font-black text-sm bg-white hover:bg-black hover:text-white transition-colors flex-shrink-0"
                onclick="this.closest('.filtro-fila').remove(); this.__gestorDup && this.__gestorDup()">✕</button>`;
      // Adjuntar referencia al gestor para el botón de eliminar
      const btnDel = fila.querySelector('button');
      btnDel.__gestorDup = _actualizarDuplicados;
      btnDel.onclick = function () { this.closest('.filtro-fila').remove(); _actualizarDuplicados(); };
      rowsContainer.appendChild(fila);
      _bindFila(fila);
      _poblarNombre(fila.querySelector('.' + nombreClass));
    }

    rowsContainer.querySelectorAll('.filtro-fila').forEach(fila => {
      // Fijar botón eliminar con referencia al actualizador
      const btn = fila.querySelector('button');
      if (btn) btn.onclick = function () { this.closest('.filtro-fila').remove(); _actualizarDuplicados(); };
      _bindFila(fila);
    });

    addBtn?.addEventListener('click', agregarFila);

    return { cargarAtributos };
  }

  // ── Lógica dinámica del formulario de OFERTAS ─────────────────
  function initOfertaFormLogic() {
    const tipo    = document.getElementById('id_oferta_tipo');
    const aplicaA = document.getElementById('id_oferta_aplica_a');
    if (!tipo || !aplicaA) return;

    function show(el, v) { if (el) el.style.display = v ? '' : 'none'; }

    const secFiltros = document.getElementById('sec_oferta_filtros');

    function updateTipo() {
      const t = tipo.value;
      show(document.getElementById('sec_oferta_pct'),      t === 'porcentaje');
      show(document.getElementById('sec_oferta_fijo'),     t === 'fijo');
      show(document.getElementById('sec_oferta_nx'),       t === 'nxprecio');
      show(document.getElementById('sec_oferta_2x1_nota'), t === '2x1');
      if (t === '2x1') {
        aplicaA.value    = 'producto';
        aplicaA.disabled = true;
        updateAplica();
      } else {
        aplicaA.disabled = false;
      }
    }

    function updateAplica() {
      const a = aplicaA.value;
      show(document.getElementById('sec_oferta_producto'),  a === 'producto');
      show(document.getElementById('sec_oferta_categoria'), a === 'categoria');
      show(secFiltros, a === 'categoria');
    }

    tipo.addEventListener('change', updateTipo);
    aplicaA.addEventListener('change', updateAplica);
    updateTipo();
    updateAplica();

    // ── Gestor de filtros atributos para oferta ────────────────
    const catSelect = document.getElementById('id_oferta_categoria');
    const gestor = crearGestorFiltros(
      document.getElementById('oferta_filtros_rows'),
      document.getElementById('btn_agregar_filtro_oferta'),
      () => catSelect?.value,
      'oferta-filtro-nombre',
      'oferta-filtro-valor',
    );
    catSelect?.addEventListener('change', () => gestor.cargarAtributos());
    if (catSelect?.value) gestor.cargarAtributos();

    // ── Typeahead de producto ──────────────────────────────────
    const buscarInput = document.getElementById('id_oferta_producto_buscar');
    const hiddenId    = document.getElementById('id_oferta_producto_id');
    const resultados  = document.getElementById('id_oferta_producto_resultados');
    let timer;

    buscarInput?.addEventListener('input', () => {
      const q = buscarInput.value.trim();
      clearTimeout(timer);
      hiddenId.value = '';
      if (q.length < 2) { resultados.classList.add('hidden'); return; }
      timer = setTimeout(async () => {
        const res  = await fetch('/ventas/api/buscar-producto/?q=' + encodeURIComponent(q));
        const data = await res.json();
        resultados.innerHTML = '';
        if (!data.length) {
          resultados.innerHTML = '<p class="px-3 py-2 text-xs font-semibold text-gray-500">Sin resultados</p>';
        } else {
          data.forEach(p => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'w-full text-left px-3 py-2 font-semibold text-sm text-black hover:bg-black hover:text-white border-b-2 border-gray-100 last:border-0 transition-colors';
            btn.textContent = p.nombre;
            btn.addEventListener('click', () => {
              hiddenId.value    = p.id;
              buscarInput.value = p.nombre;
              resultados.classList.add('hidden');
            });
            resultados.appendChild(btn);
          });
        }
        resultados.classList.remove('hidden');
      }, 280);
    });

    document.addEventListener('click', function _cerrarResultados(e) {
      if (!e.target.closest('#sec_oferta_producto')) {
        resultados?.classList.add('hidden');
      }
    });
  }

  // ── Lógica dinámica del formulario de PAQUETES / REGALOS ──────
  function initFormLogic() {
    const condSelect   = document.getElementById('id_tipo_condicion');
    const resSelect    = document.getElementById('id_tipo_resultado');
    const secCatDisp   = document.getElementById('sec_categoria_disparadora');
    const secMonto     = document.getElementById('sec_monto_minimo');
    const secProdReg   = document.getElementById('sec_producto_regalo');
    const secCatReg    = document.getElementById('sec_categoria_regalo');
    const secFiltro    = document.getElementById('sec_filtro_atributo');
    const notaCatHer   = document.getElementById('nota_cat_heredada');
    const catRegSelect = document.getElementById('id_categoria_regalo');
    if (!condSelect || !resSelect) return;

    function show(el, visible) { if (el) el.style.display = visible ? '' : 'none'; }

    function actualizarCondicion() {
      const val = condSelect.value;
      show(secCatDisp, val === 'categoria' || val === 'monto_categoria');
      show(secMonto,   val === 'monto'     || val === 'monto_categoria');
      actualizarResultado();
    }

    function actualizarResultado() {
      const valRes     = resSelect.value;
      const esMontoCat = condSelect.value === 'monto_categoria';
      show(secProdReg, valRes === 'regalo_fijo');
      if (valRes === 'regalo_variante' && esMontoCat) {
        show(secCatReg,  false);
        show(secFiltro,  false);
        show(notaCatHer, true);
      } else if (valRes === 'regalo_variante') {
        show(secCatReg,  true);
        show(secFiltro,  true);
        show(notaCatHer, false);
      } else {
        show(secCatReg,  false);
        show(secFiltro,  false);
        show(notaCatHer, false);
      }
    }

    // ── Gestor de filtros atributos para paquete ───────────────
    const gestor = crearGestorFiltros(
      document.getElementById('promo_filtros_rows'),
      document.getElementById('btn_agregar_filtro_promo'),
      () => catRegSelect?.value,
      'promo-filtro-nombre',
      'promo-filtro-valor',
    );
    catRegSelect?.addEventListener('change', () => gestor.cargarAtributos());

    condSelect.addEventListener('change', actualizarCondicion);
    resSelect.addEventListener('change',  actualizarResultado);
    actualizarCondicion();

    if (catRegSelect?.value) gestor.cargarAtributos();
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    document.querySelectorAll('.prom-tab[data-seccion="paquete"]').forEach(tab => {
      tab.addEventListener('click', () => filtrar(tab.dataset.tipo));
    });

    document.querySelectorAll('.prom-tab[data-seccion="oferta"]').forEach(tab => {
      tab.addEventListener('click', () => filtrarOfertas(tab.dataset.tipo));
    });

    document.getElementById('modalPromocion')?.addEventListener('click', function (e) {
      if (e.target === this) cerrarModal();
    });
    document.getElementById('modalConfirmar')?.addEventListener('click', function (e) {
      if (e.target === this) cerrarConfirmar();
    });

    actualizarConteos();
    filtrar('todos', false);
    actualizarConteosOfertas();
    filtrarOfertas('todos', false);
  }

  // ── API pública ────────────────────────────────────────────────
  const API = {
    nueva: nuevaPromo,
    editar: editarPromo,
    toggle: togglePromo,
    confirmarEliminar,
    cerrarConfirmar,
    ejecutarEliminar,
    cerrarModal,
    enviarPromocion,
    setModo,
    nuevaOferta,
    editarOferta,
    toggleOferta,
  };

  window.PromocionesPage = API;
  // Aliases para llamadas desde los forms cargados por AJAX
  window.enviarPromocion = enviarPromocion;
  window.enviarOferta    = enviarOferta;
  window.cerrarModal     = cerrarModal;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
