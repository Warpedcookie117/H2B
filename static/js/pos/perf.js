// perf.js — Diagnóstico: detecta CUÁNDO se pasma el POS y QUÉ operación lo causó.
// Solo deja logs en la consola (no cambia comportamiento). Quitar cuando ya
// no se necesite.
//
// Cómo leerlo en la consola cuando se pasme:
//   🧊 BLOQUEO / FREEZE  → el hilo se congeló N ms. Trae "última operación".
//   ⏱️ "<op>" tardó Nms   → una operación puntual (paginar, buscar…) se tardó.
//   WS <N> mensajes en 1s → posible avalancha de mensajes del WebSocket.

console.log("[POS:perf] Módulo cargado");

// Última operación registrada por los módulos (migas de pan) para atribuir
// un bloqueo a lo que estaba pasando justo antes.
let ultimaOp = { label: "(arranque)", t: performance.now() };

function marca(label) {
    ultimaOp = { label, t: performance.now() };
}

export function initPerf() {
    // Expuesto como global para que cualquier módulo lo use sin imports:
    //   window.__posPerf?.marca("lo que estoy haciendo")
    window.__posPerf = { marca };

    // 1) Detector de TAREAS LARGAS (bloqueos del hilo principal). La API
    //    'longtask' reporta cualquier tarea > 50ms; avisamos desde 120ms.
    if ("PerformanceObserver" in window) {
        try {
            const obs = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.duration >= 120) {
                        const hace = (performance.now() - ultimaOp.t).toFixed(0);
                        console.warn(
                            `[POS:perf] 🧊 BLOQUEO ${entry.duration.toFixed(0)}ms — ` +
                            `última operación: "${ultimaOp.label}" (hace ${hace}ms)`
                        );
                    }
                }
            });
            obs.observe({ entryTypes: ["longtask"] });
            console.log("[POS:perf] observando tareas largas ✓");
        } catch (e) {
            console.warn("[POS:perf] longtask no soportado en este navegador:", e);
        }
    }

    // 2) WATCHDOG: debería latir cada 1s. Si late tarde, el hilo estuvo
    //    congelado ese tiempo (esto SÍ atrapa freezes duros que a veces
    //    'longtask' no reporta). Reporta con la última operación.
    let ultimoLatido = performance.now();
    setInterval(() => {
        const ahora   = performance.now();
        const atraso  = ahora - ultimoLatido - 1000;
        ultimoLatido  = ahora;
        if (atraso > 400) {
            const hace = (ahora - ultimaOp.t).toFixed(0);
            console.warn(
                `[POS:perf] 🧊 FREEZE ~${atraso.toFixed(0)}ms — ` +
                `última operación: "${ultimaOp.label}" (hace ${hace}ms)`
            );
        }
    }, 1000);

    console.log("[POS:perf] watchdog activo ✓");
}
