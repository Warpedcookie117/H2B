// ===============================
// Reportes — AJAX, subcategorías, toast, PDF dinámico
// ===============================

document.addEventListener('DOMContentLoaded', function () {

    const form      = document.getElementById('form-reportes');
    const catSelect = document.getElementById('categoria');
    const subSelect = document.getElementById('subcategoria');
    if (!form || !catSelect || !subSelect) return;

    const apiUrl = form.dataset.apiUrl || '/inventario/api/categorias/';

    let categoriasCache = null;
    let fetchActivo     = null;
    let toastTimer      = null;

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

    // Categoría — carga subcategorías antes de buscar
    catSelect.addEventListener('change', async function () {
        await cargarSubcategorias(this.value, null);
        fetchReporte(getLabelFiltro(this));
    });

    // Resto de selects
    form.querySelectorAll('select').forEach(function (select) {
        if (select === catSelect) return;
        select.addEventListener('change', function () {
            fetchReporte(getLabelFiltro(this));
        });
    });

    // ==============================
    // INIT
    // ==============================
    const filtroSub = subSelect.dataset.selected || '';
    if (catSelect.value) {
        cargarSubcategorias(catSelect.value, filtroSub);
    }
    actualizarLinkPDF();

});
