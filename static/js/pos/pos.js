// pos.js — Orquestador general del POS

import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initUI } from "./ui.js";
import { initImpresion } from "./impresion.js";
import { initConsultaPrecios } from "./consulta_precios.js";
import { initStock } from "./stock.js";

document.addEventListener("DOMContentLoaded", () => {

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
