// ===============================
// Reportes — AJAX, subcategorías, toast, PDF dinámico
// ===============================

document.addEventListener('DOMContentLoaded', function () {

    const form      = document.getElementById('form-reportes');
    const catSelect = document.getElementById('categoria');
    const subSelect = document.getElementById('subcategoria');
    if (!form || !catSelect || !subSelect) return;

    const apiUrl = form.dataset.apiUrl || '/inventario/api/categorias/';

    // Filtro por atributos (bajo demanda al elegir subcategoría)
    const attrUrlBase    = form.dataset.attrUrl || '';   // .../subcategoria/0/atributos-valores/
    const panelAtributos = document.getElementById('panel-atributos-reportes');
    const atributosRows  = document.getElementById('atributos-rows-reportes');
    let attrParesInit = [];
    try {
        attrParesInit = JSON.parse(document.getElementById('attr-pares-reportes-json')?.textContent || '[]');
    } catch (e) { attrParesInit = []; }

    let categoriasCache = null;
    let fetchActivo     = null;
    let toastTimer      = null;

    // ==============================
    // PANEL DE ATRIBUTOS
    // ==============================
    async function cargarAtributosPanel(subcatId, preseleccion = []) {
        if (!panelAtributos || !atributosRows) return;
        atributosRows.innerHTML = '';
        if (!subcatId) { panelAtributos.classList.add('hidden'); return; }

        const url = attrUrlBase.replace('/0/', '/' + subcatId + '/');
        let atributos = [];
        try {
            const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await resp.json();
            atributos = data.atributos || [];
        } catch (e) { console.error('Error atributos:', e); }

        if (!atributos.length) { panelAtributos.classList.add('hidden'); return; }
        panelAtributos.classList.remove('hidden');

        const preMap = {};
        preseleccion.forEach(([n, v]) => { preMap[n] = v; });

        atributos.forEach(a => {
            const wrap = document.createElement('div');

            const label = document.createElement('label');
            label.className = 'block font-black text-black text-xs uppercase tracking-widest mb-1.5';
            label.textContent = a.nombre;

            const sel = document.createElement('select');
            sel.dataset.attr = a.nombre;   // sin name: no entra a FormData, se maneja aparte
            sel.className = 'select-90s';

            const opt0 = document.createElement('option');
            opt0.value = '';
            opt0.textContent = 'Cualquiera';
            sel.appendChild(opt0);

            (a.valores || []).forEach(v => {
                const opt = document.createElement('option');
                opt.value = v;
                opt.textContent = v;
                if (preMap[a.nombre] === v) opt.selected = true;
                sel.appendChild(opt);
            });

            sel.addEventListener('change', () => fetchReporte('Atributo: ' + a.nombre));

            wrap.appendChild(label);
            wrap.appendChild(sel);
            atributosRows.appendChild(wrap);
        });
    }

    function agregarAtributosAUrl(searchParams) {
        // Filtro por subcategoría (an/av)
        document.querySelectorAll('#atributos-rows-reportes select[data-attr]').forEach(sel => {
            if (sel.value) {
                searchParams.append('an', sel.dataset.attr);
                searchParams.append('av', sel.value);
            }
        });
        // Filtro global por atributo (gan/gav)
        const gNombre = document.getElementById('global-attr-nombre');
        const gValor  = document.getElementById('global-attr-valor');
        if (gNombre && gValor && gNombre.value && gValor.value) {
            searchParams.append('gan', gNombre.value);
            searchParams.append('gav', gValor.value);
        }
    }

    // ==============================
    // FILTRO GLOBAL POR ATRIBUTO
    // ==============================
    const globalAttrUrl  = form.dataset.globalAttrUrl || '';
    const gBuscar        = document.getElementById('global-attr-buscar');
    const gNombreHidden  = document.getElementById('global-attr-nombre');
    const gResultados    = document.getElementById('global-attr-resultados');
    const gValorSel      = document.getElementById('global-attr-valor');

    let atributoNombres = [];   // ordenados por coincidencia entre subcategorías
    try {
        atributoNombres = JSON.parse(document.getElementById('atributo-nombres-json')?.textContent || '[]');
    } catch (e) { atributoNombres = []; }

    // Ignora acentos y mayúsculas al buscar ("tamano" encuentra "TAMAÑO")
    function _normalizar(t) {
        return (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    // Lista de coincidencias: vacío → top 5 más compartidos; con texto → busca en TODOS
    function renderResultadosGlobal(filtro) {
        if (!gResultados) return;
        const f = _normalizar((filtro || '').trim());
        const lista = f
            ? atributoNombres.filter(n => _normalizar(n).includes(f)).slice(0, 12)
            : atributoNombres.slice(0, 5);

        gResultados.innerHTML = '';
        if (!lista.length) {
            gResultados.innerHTML = '<p class="px-3 py-2 text-xs font-semibold text-gray-500">Sin coincidencias</p>';
            gResultados.classList.remove('hidden');
            return;
        }
        if (!f) {
            const h = document.createElement('p');
            h.className = 'px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-gray-400 bg-gray-50';
            h.textContent = 'Los más usados entre categorías';
            gResultados.appendChild(h);
        }
        lista.forEach(n => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'w-full text-left px-3 py-2 font-bold text-sm text-black hover:bg-black hover:text-white border-b-2 border-gray-100 last:border-0 transition-colors';
            b.textContent = n;
            b.addEventListener('click', () => seleccionarAtributoGlobal(n));
            gResultados.appendChild(b);
        });
        gResultados.classList.remove('hidden');
    }

    function seleccionarAtributoGlobal(nombre) {
        gBuscar.value = nombre;
        gNombreHidden.value = nombre;
        gResultados.classList.add('hidden');
        cargarGlobalValores(nombre);   // carga los valores de ese atributo
        fetchReporte('Atributo global: ' + nombre);
    }

    async function cargarGlobalValores(nombre, preValor = '') {
        if (!gValorSel) return;
        if (!nombre) {
            gValorSel.innerHTML = '<option value="">— Elige atributo primero —</option>';
            gValorSel.disabled = true;
            return;
        }
        gValorSel.innerHTML = '<option value="">Cargando...</option>';
        gValorSel.disabled = true;
        try {
            const url = globalAttrUrl + '?nombre=' + encodeURIComponent(nombre);
            const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await resp.json();
            let html = '<option value="">Cualquiera</option>';
            (data.valores || []).forEach(v => {
                const sel = (v === preValor) ? ' selected' : '';
                html += `<option value="${v}"${sel}>${v}</option>`;
            });
            gValorSel.innerHTML = html;
            gValorSel.disabled = false;
        } catch (e) {
            console.error('Error valores globales:', e);
            gValorSel.innerHTML = '<option value="">Error al cargar</option>';
        }
    }

    // ==============================
    // SUBCATEGORÍAS
    // ==============================
    async function cargarSubcategorias(categoriaId, filtroSub) {
        if (!categoriaId) {
            subSelect.innerHTML = '<option value="">Todas</option>';
            return;
        }
        subSelect.innerHTML = '<option value="">Cargando...</option>';
        try {
            if (!categoriasCache) {
                const resp = await fetch(apiUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                categoriasCache = await resp.json();
            }
            const cat = categoriasCache.categorias_padre.find(c => String(c.id) === String(categoriaId));
            let html = '<option value="">Todas</option>';
            if (cat && cat.subcategorias) {
                cat.subcategorias.forEach(s => {
                    html += `<option value="${s.id}">${s.nombre}</option>`;
                });
            }
            subSelect.innerHTML = html;
            if (filtroSub) {
                const opt = subSelect.querySelector(`option[value="${filtroSub}"]`);
                if (opt) opt.selected = true;
            }
        } catch (err) {
            console.error('Error subcategorías:', err);
            subSelect.innerHTML = '<option value="">Error al cargar</option>';
        }
    }

    // ==============================
    // TOAST
    // ==============================
    function mostrarToast(texto) {
        const toast = document.getElementById('reportes-toast');
        if (!toast) return;
        toast.textContent = texto;
        toast.classList.remove('hidden');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.add('hidden'), 2500);
    }

    // ==============================
    // PDF LINK — sincronizar con filtros activos
    // ==============================
    function actualizarLinkPDF() {
        const link = document.getElementById('link-pdf');
        if (!link) return;
        const params = new URLSearchParams();
        new FormData(form).forEach((val, key) => { if (val) params.set(key, val); });
        agregarAtributosAUrl(params);   // an/av del panel de atributos
        link.href = link.dataset.base + '?' + params.toString();
    }

    // ==============================
    // FETCH RESULTADOS
    // ==============================
    async function fetchReporte(labelFiltro, pagina) {
        mostrarToast('✅ ' + labelFiltro);

        if (fetchActivo) fetchActivo.abort();
        fetchActivo = new AbortController();

        const url = new URL(window.location.href);
        url.search = '';
        new FormData(form).forEach((val, key) => { if (val) url.searchParams.set(key, val); });
        agregarAtributosAUrl(url.searchParams);   // an/av + gan/gav
        // Al cambiar un filtro no se manda página → vuelve a la 1. Solo los
        // botones de paginación mandan `pagina`.
        if (pagina) url.searchParams.set('page', pagina);

        try {
            const res   = await fetch(url.toString(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal:  fetchActivo.signal,
            });
            const html  = await res.text();
            const doc   = new DOMParser().parseFromString(html, 'text/html');
            const nuevo = doc.getElementById('reportes-resultado');
            const actual = document.getElementById('reportes-resultado');
            if (nuevo && actual) actual.innerHTML = nuevo.innerHTML;
            actualizarLinkPDF();
            window.history.replaceState(null, '', url.toString());
        } catch (e) {
            if (e.name !== 'AbortError') console.error('Error reporte:', e);
        }
    }

    // ==============================
    // LABELS PARA TOAST
    // ==============================
    const LABELS = {
        tipo:        'Tipo de reporte',
        categoria:   'Categoría',
        subcategoria:'Subcategoría',
        temporada:   'Temporada',
        ubicacion:   'Ubicación',
        movimiento:  'Tipo de movimiento',
    };

    function getLabelFiltro(select) {
        const nombre = LABELS[select.name] || select.name;
        const valor  = select.options[select.selectedIndex]?.text || 'Todos';
        return `${nombre}: ${valor}`;
    }

    // ==============================
    // EVENTOS
    // ==============================

    // Prevenir submit normal del form
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        fetchReporte('Reporte actualizado');
    });

    // Paginación — botones dentro de #reportes-resultado (se re-renderiza por
    // AJAX, por eso escuchamos en el contenedor estable con delegación).
    const resultadoBox = document.getElementById('reportes-resultado');
    resultadoBox?.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-page]');
        if (!btn) return;
        fetchReporte('Página ' + btn.dataset.page, btn.dataset.page);
        resultadoBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // Categoría — carga subcategorías antes de buscar. Al cambiar de
    // categoría la subcategoría se resetea, así que el panel de atributos
    // se limpia también.
    catSelect.addEventListener('change', async function () {
        await cargarSubcategorias(this.value, null);
        cargarAtributosPanel('');
        fetchReporte(getLabelFiltro(this));
    });

    // Subcategoría — pinta el panel de atributos de esa subcategoría (fresco,
    // sin preselección) y luego busca.
    subSelect.addEventListener('change', async function () {
        await cargarAtributosPanel(this.value);
        fetchReporte(getLabelFiltro(this));
    });

    // Filtro global — buscador de atributo:
    gBuscar?.addEventListener('focus', function () { renderResultadosGlobal(this.value); });
    gBuscar?.addEventListener('input', function () {
        renderResultadosGlobal(this.value);
        // Si vacían el campo, se quita el filtro global.
        if (!this.value.trim() && gNombreHidden.value) {
            gNombreHidden.value = '';
            cargarGlobalValores('');
            fetchReporte('Filtro global quitado');
        }
    });
    // Cerrar el dropdown al picar fuera
    document.addEventListener('click', function (e) {
        if (!e.target.closest('#global-attr-buscar') && !e.target.closest('#global-attr-resultados')) {
            gResultados?.classList.add('hidden');
        }
    });
    // Al elegir un valor del atributo global, buscar
    gValorSel?.addEventListener('change', function () {
        fetchReporte('Filtro global');
    });

    // Resto de selects (excepto categoría, subcategoría y el valor global,
    // ya manejados arriba)
    form.querySelectorAll('select').forEach(function (select) {
        if (select === catSelect || select === subSelect) return;
        if (select === gValorSel) return;
        select.addEventListener('change', function () {
            fetchReporte(getLabelFiltro(this));
        });
    });

    // ==============================
    // INIT
    // ==============================
    const filtroSub = subSelect.dataset.selected || '';
    if (catSelect.value) {
        // Cargar subcategorías; al terminar, si había subcategoría
        // preseleccionada, pintar sus atributos con los valores ya elegidos.
        cargarSubcategorias(catSelect.value, filtroSub).then(() => {
            if (filtroSub) cargarAtributosPanel(filtroSub, attrParesInit);
        });
    }

    // Filtro global: restaurar selección si venía en la URL (recarga/paginación).
    let attrGlobalInit = [];
    try {
        attrGlobalInit = JSON.parse(document.getElementById('attr-global-reportes-json')?.textContent || '[]');
    } catch (e) { attrGlobalInit = []; }
    if (attrGlobalInit.length && gBuscar && gNombreHidden) {
        const [gn, gv] = attrGlobalInit[0];
        gBuscar.value = gn;
        gNombreHidden.value = gn;
        cargarGlobalValores(gn, gv);
    }

    actualizarLinkPDF();

});
