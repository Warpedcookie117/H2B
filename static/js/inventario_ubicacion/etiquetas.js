// build: 2026-05-21T01:00 — fuerza nuevo hash en ManifestStaticFilesStorage
// ============================
// Mostrar / ocultar etiqueta
// ============================
window.mostrarEtiquetaInterna = function (button) {
  const url         = button.getAttribute("data-url");
  const productoId  = button.getAttribute("data-id");
  const ubicacionId = button.getAttribute("data-ubicacion");

  const contenedor = document.getElementById(`etiqueta-${productoId}-${ubicacionId}`);
  const img        = document.getElementById(`img-${productoId}-${ubicacionId}`);

  if (!contenedor || !img) {
    console.error("❌ No se encontró contenedor o img para:", productoId, ubicacionId);
    return;
  }

  const isOpen = contenedor.dataset.open === "true";

  if (isOpen) {
    contenedor.dataset.open    = "false";
    contenedor.style.maxHeight = "0";
    contenedor.style.opacity   = "0";
    contenedor.style.padding   = "0";
    return;
  }

  contenedor.dataset.open    = "true";
  contenedor.style.maxHeight = "600px";
  contenedor.style.opacity   = "1";
  contenedor.style.padding   = "8px";

  // Solo fetch si la imagen no está cargada.
  // Cache-busting con timestamp: forza al browser/CDN a pedir la versión
  // fresca después de cada deploy en lugar de servir la imagen vieja cacheada.
  if (!img.src || img.src === window.location.href) {
    const separator = url.includes("?") ? "&" : "?";
    const fetchUrl = `${url}${separator}t=${Date.now()}`;
    fetch(fetchUrl, { cache: "no-store" })
      .then(res => res.json())
      .then(data => {
        if (data.imagen) {
          const mime = data.mime || "image/png";
          img.src = `data:${mime};base64,${data.imagen}`;
        } else {
          img.alt = "Etiqueta no disponible";
        }
      })
      .catch(err => {
        img.alt = "Error al cargar";
        console.error("❌ Error fetch etiqueta:", err);
      });
  }
};

// ============================
// Copiar código al hacer clic
// ============================
document.addEventListener("click", function (e) {
  if (e.target && e.target.id.startsWith("codigo-")) {
    navigator.clipboard.writeText(e.target.innerText.trim())
      .then(() => {
        e.target.style.background = "#06D6A0";
        setTimeout(() => e.target.style.background = "", 500);
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
  if (!img || !img.src || img.src === window.location.href) return;

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

window.descargarEtiquetaPDF = async function (url, codigo) {
  try {
    const r = await fetch(url);
    const blob = await r.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `etiqueta_${codigo}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  } catch (e) {
    console.error("Error descargando PDF:", e);
  }
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
// Guardar etiqueta a Galería (iOS Fotos / Android Galería)
// Print Master detecta JPG/JPEG en la galería del dispositivo.
// Usamos Web Share API para que iOS abra el sheet nativo donde el usuario
// elige "Guardar imagen" (→ Fotos) o "Guardar en Archivos".
// ============================
window.descargarEtiqueta = async function (productoId, ubicacionId) {
  const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
  if (!img || !img.src || img.src === window.location.href) {
    alert("Primero abre la etiqueta tocando 'Etiqueta'.");
    return;
  }

  // Determinar extensión y tipo MIME desde el data URL (JPG para code128,
  // PNG para EAN/UPC).
  const mimeMatch = img.src.match(/^data:([^;]+);/);
  const mime = mimeMatch ? mimeMatch[1] : "image/jpeg";
  const ext = mime === "image/png" ? "png" : "jpg";

  // 1. Web Share API: iOS Safari abre el sheet nativo con opciones
  //    "Guardar imagen" (→ Fotos) y "Guardar en Archivos". El usuario elige.
  try {
    const blob = await (await fetch(img.src)).blob();
    const file = new File([blob], `etiqueta_${productoId}.${ext}`, { type: mime });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({
        files: [file],
        title: "Etiqueta",
        text: "Guarda en Fotos y ábrela con Print Master",
      });
      return;
    }
  } catch (e) {
    console.warn("[etiqueta] Web Share no disponible o cancelado:", e);
  }

  // 2. Fallback: abrir la imagen sola en pantalla completa con instrucción
  //    para long-press → "Guardar en Fotos".
  const ventana = window.open("", "_blank");
  if (!ventana) {
    alert("Activa los pop-ups para guardar la etiqueta.");
    return;
  }
  ventana.document.write(`
    <html>
      <head>
        <title>Etiqueta</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
          body { margin:0; padding:1rem; background:#FFBE0B; font-family:system-ui,sans-serif; }
          .instruccion {
            background:#000; color:#fff;
            padding:1rem; margin-bottom:1rem;
            border:4px solid black;
            box-shadow:6px 6px 0 0 #FF006E;
            font-weight:900; text-align:center;
            font-size:.95rem; line-height:1.4;
            text-transform:uppercase; letter-spacing:.04em;
          }
          img {
            width:100%; display:block;
            border:4px solid black;
            box-shadow:6px 6px 0 0 black;
            background:white;
          }
        </style>
      </head>
      <body>
        <div class="instruccion">
          📱 Mantén presionado la imagen<br>
          → "Guardar en Fotos"<br>
          luego ábrela desde Print Master
        </div>
        <img src="${img.src}" />
      </body>
    </html>
  `);
  ventana.document.close();
};