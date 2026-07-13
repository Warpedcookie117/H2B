// mostrarEtiqueta.js — reutilizable para cualquier template

document.addEventListener("DOMContentLoaded", function () {

  // ============================
  // Mostrar / ocultar etiqueta
  // ============================
  window.mostrarEtiquetaInterna = function (button) {
    const url         = button.getAttribute("data-url");
    const productoId  = button.getAttribute("data-id");
    const ubicacionId = button.getAttribute("data-ubicacion");

    console.log("=== mostrarEtiquetaInterna ===");
    console.log("productoId:", productoId);
    console.log("ubicacionId:", ubicacionId);
    console.log("url:", url);
    console.log("window.innerWidth:", window.innerWidth);

    const contenedor = document.getElementById(`etiqueta-${productoId}-${ubicacionId}`);
    const img        = document.getElementById(`img-${productoId}-${ubicacionId}`);

    console.log("contenedor encontrado:", !!contenedor, contenedor);
    console.log("img encontrado:", !!img, img);

    if (!contenedor || !img) {
      console.error("❌ No se encontró el contenedor o img — verifica los IDs en el HTML");
      return;
    }

    const isOpen = contenedor.dataset.open === "true";
    console.log("isOpen:", isOpen);
    console.log("contenedor.style.maxHeight actual:", contenedor.style.maxHeight);
    console.log("contenedor clases:", contenedor.className);

    if (isOpen) {
      contenedor.dataset.open    = "false";
      contenedor.style.maxHeight = "0";
      contenedor.style.opacity   = "0";
      contenedor.style.padding   = "0";
      console.log("✅ CERRANDO etiqueta");
      return;
    }

    contenedor.dataset.open    = "true";
    contenedor.style.maxHeight = "600px";
    contenedor.style.opacity   = "1";
    contenedor.style.padding   = "8px";
    console.log("✅ ABRIENDO etiqueta");
    console.log("contenedor.style.maxHeight después:", contenedor.style.maxHeight);

    if (!img.src || img.src === window.location.href) {
      console.log("📡 Haciendo fetch a:", url);
      fetch(url)
        .then(res => {
          console.log("fetch status:", res.status);
          return res.json();
        })
        .then(data => {
          console.log("data keys:", Object.keys(data));
          if (data.imagen) {
            img.src = `data:image/png;base64,${data.imagen}`;
            console.log("✅ Imagen cargada correctamente");
          } else {
            img.alt = "Etiqueta no disponible";
            console.warn("⚠️ No vino campo 'imagen' en la respuesta:", data);
          }
        })
        .catch(err => {
          img.alt = "Error al cargar";
          console.error("❌ Error en fetch:", err);
        });
    } else {
      console.log("ℹ️ Imagen ya cargada, src:", img.src.substring(0, 60));
    }
  };

  window.mostrarEtiqueta = window.mostrarEtiquetaInterna;

  // ============================
  // Copiar código al hacer clic
  // ============================
  document.addEventListener("click", function (e) {
    if (e.target && e.target.id.startsWith("codigo-")) {
      navigator.clipboard.writeText(e.target.innerText.trim())
        .then(() => {
          e.target.classList.add("bg-green-300");
          setTimeout(() => e.target.classList.remove("bg-green-300"), 500);
        })
        .catch(err => console.error("Error al copiar:", err));
    }
  });

  // ============================
  // Imprimir etiqueta
  // ============================
  const _AGENT_URL = "http://127.0.0.1:12345";

  window.imprimirEtiqueta = async function (productoId, ubicacionId) {
    const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
    if (!img || !img.src) return;

    let printer = localStorage.getItem("pos_impresora_etiquetas") || "";

    if (!printer) {
      const nombre = prompt(
        "Ingresa el nombre exacto de la impresora de etiquetas\n" +
        "(como aparece en Configuración → Bluetooth y dispositivos → Impresoras):"
      );
      if (!nombre || !nombre.trim()) return;
      printer = nombre.trim();
      localStorage.setItem("pos_impresora_etiquetas", printer);
    }

    try {
      const base64 = img.src.includes(",") ? img.src.split(",")[1] : img.src;
      const r = await fetch(`${_AGENT_URL}/print-label`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagen_base64: base64, printer }),
        signal: AbortSignal.timeout(5000),
      });
      const d = await r.json();
      if (d.ok) return;
      console.warn("Agente error al imprimir etiqueta:", d.error);
    } catch {
      console.warn("Agente POS no disponible, usando ventana de impresión");
    }

    // Fallback: ventana de impresión del navegador
    const ventana = window.open("", "_blank");
    ventana.document.write(`
      <html>
        <head><title>Etiqueta</title>
          <style>
            body { margin:0; display:flex; justify-content:center; align-items:center; height:100vh; }
            img  { max-width:100%; max-height:100%; }
          </style>
        </head>
        <body>
          <img src="${img.src}" />
          <script>
            window.onload = function() {
              window.print();
              window.onafterprint = function() { window.close(); };
            };
          <\/script>
        </body>
      </html>
    `);
    ventana.document.close();
  };

  window.configurarImpresoraEtiquetas = function () {
    const actual = localStorage.getItem("pos_impresora_etiquetas") || "(sin configurar)";
    const nombre = prompt(`Impresora de etiquetas actual: ${actual}\n\nIngresa el nuevo nombre (deja vacío para borrar la configuración):`);
    if (nombre === null) return;
    if (nombre.trim()) {
      localStorage.setItem("pos_impresora_etiquetas", nombre.trim());
      alert(`Impresora guardada: ${nombre.trim()}`);
    } else {
      localStorage.removeItem("pos_impresora_etiquetas");
      alert("Configuración de impresora de etiquetas eliminada.");
    }
  };

  // ============================
  // Descargar etiqueta
  // ============================
  window.descargarEtiqueta = function (productoId, ubicacionId) {
    const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
    if (!img || !img.src) return;

    const enlace = document.createElement("a");
    enlace.href     = img.src;
    enlace.download = `etiqueta_${productoId}_${ubicacionId}.png`;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
  };

});