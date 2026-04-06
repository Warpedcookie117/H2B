// pos.js — Orquestador general del POS

import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initUI } from "./ui.js";
import { initImpresion } from "./impresion.js"; // Impresora térmica

document.addEventListener("DOMContentLoaded", () => {

    // Productos
    initBuscador();
    initDragDrop();
    initEscaneo();

    // UI general del carrito
    initUI();

    // Impresora térmica
    initImpresion();
});
