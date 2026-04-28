// pos.js — Orquestador general del POS

import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initUI } from "./ui.js";
import { initImpresion } from "./impresion.js";
import { initConsultaPrecios } from "./consulta_precios.js";
import { initStock } from "./stock.js";
import { initPaginacion } from "./paginacion.js";
import { initPromociones } from "./promociones.js";
import { initOfertas }    from "./ofertas.js";

document.addEventListener("DOMContentLoaded", () => {

    initPaginacion();

    initBuscador();
    initDragDrop();
    initEscaneo();

    initUI();
    initImpresion();
    initConsultaPrecios();
    initStock();
    initPromociones();
    initOfertas();
});
