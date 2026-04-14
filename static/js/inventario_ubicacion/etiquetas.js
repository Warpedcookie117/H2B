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

  // Solo fetch si la imagen no está cargada
  if (!img.src || img.src === window.location.href) {
    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (data.imagen) {
          img.src = `data:image/png;base64,${data.imagen}`;
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
window.imprimirEtiqueta = function (productoId, ubicacionId) {
  const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
  if (!img || !img.src || img.src === window.location.href) return;

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

// ============================
// Descargar etiqueta
// ============================
window.descargarEtiqueta = function (productoId, ubicacionId) {
  const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
  if (!img || !img.src || img.src === window.location.href) return;

  const enlace = document.createElement("a");
  enlace.href     = img.src;
  enlace.download = `etiqueta_${productoId}_${ubicacionId}.png`;
  document.body.appendChild(enlace);
  enlace.click();
  document.body.removeChild(enlace);
};