// pos.js — Orquestador general del POS

import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initUI } from "./ui.js";
import { initImpresion } from "./impresion.js";
import { initConsultaPrecios } from "./consulta_precios.js";
import { initStock } from "./stock.js";
import { initPaginacion } from "./paginacion.js";
import { initPromociones } from "./promociones.js";
import { initOfertas }    from "./ofertas.js";

console.log("[POS] Módulo pos.js cargado");

document.addEventListener("DOMContentLoaded", () => {
    console.log("[POS] DOMContentLoaded — iniciando módulos...");

    initPaginacion();
    console.log("[POS] ✓ paginacion init");

    initBuscador();
    console.log("[POS] ✓ buscador init");

    initDragDrop();
    console.log("[POS] ✓ dragdrop init");

    initEscaneo();
    console.log("[POS] ✓ escaneo init");

    initUI();
    console.log("[POS] ✓ ui init");

    initImpresion();
    console.log("[POS] ✓ impresion init");

    initConsultaPrecios();
    console.log("[POS] ✓ consulta_precios init");

    initStock();
    console.log("[POS] ✓ stock init");

    initPromociones();
    console.log("[POS] ✓ promociones init");

    initOfertas();
    console.log("[POS] ✓ ofertas init");

    console.log("[POS] 🚀 Todo iniciado correctamente");
});
