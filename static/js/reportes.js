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
        document.querySelectorAll('#atributos-rows-reportes select[data-attr]').forEach(sel => {
            if (sel.value) {
                searchParams.append('an', sel.dataset.attr);
                searchParams.append('av', sel.value);
            }
        });
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
    async function fetchReporte(labelFiltro) {
        mostrarToast('✅ ' + labelFiltro);

        if (fetchActivo) fetchActivo.abort();
        fetchActivo = new AbortController();

        const url = new URL(window.location.href);
        url.search = '';
        new FormData(form).forEach((val, key) => { if (val) url.searchParams.set(key, val); });
        agregarAtributosAUrl(url.searchParams);   // an/av del panel de atributos

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

    // Resto de selects (excepto categoría y subcategoría, ya manejadas arriba)
    form.querySelectorAll('select').forEach(function (select) {
        if (select === catSelect || select === subSelect) return;
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
    actualizarLinkPDF();

});
