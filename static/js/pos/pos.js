// pos.js — Orquestador general del POS

import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initUI } from "./ui.js";
import { initImpresion } from "./impresion.js";
import { initConsultaPrecios } from "./consulta_precios.js";
import { initStock } from "./stock.js";
import { initPaginacion } from "./paginacion.js";

document.addEventListener("DOMContentLoaded", () => {

    // Paginación del grid (debe ir antes que el buscador)
    initPaginacion();

    // Productos
    initBuscador();
    initDragDrop();
    initEscaneo();

    // UI general del carrito
    initUI();

    // Impresora térmica
    initImpresion();

    // Consulta de precios (tecla E)
    initConsultaPrecios();

    // Stock en tiempo real
    initStock();
});
