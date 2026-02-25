document.addEventListener("DOMContentLoaded", function () {

  // ============================
  // Mostrar etiqueta interna con animación suave
  // ============================
  window.mostrarEtiquetaInterna = function (button) {
    const url = button.getAttribute("data-url");
    const productoId = button.getAttribute("data-id");
    const ubicacionId = button.getAttribute("data-ubicacion");

    const contenedor = document.getElementById(`etiqueta-${productoId}-${ubicacionId}`);
    const img = document.getElementById(`img-${productoId}-${ubicacionId}`);

    if (!contenedor || !img) return;

    const isOpen = contenedor.classList.contains("open");

    // ============================
    // CERRAR (animación suave)
    // ============================
    if (isOpen) {
      contenedor.classList.remove("open");
      contenedor.classList.add("max-h-0", "opacity-0", "p-0");
      contenedor.classList.remove("p-3");
      return;
    }

    // ============================
    // ABRIR (animación suave)
    // ============================
    contenedor.classList.add("open");
    contenedor.classList.remove("max-h-0", "opacity-0", "p-0");
    contenedor.classList.add("p-3");

    // ============================
    // Cargar imagen base64
    // ============================
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
        img.alt = "Error al cargar la etiqueta";
        console.error(err);
      });
  };

  // ============================
  // Copiar código automáticamente al hacer clic
  // ============================
  document.addEventListener("click", function (e) {
    if (e.target && e.target.id.startsWith("codigo-")) {
      const texto = e.target.innerText.trim();

      navigator.clipboard.writeText(texto)
        .then(() => {
          e.target.classList.add("bg-green-300");
          setTimeout(() => {
            e.target.classList.remove("bg-green-300");
          }, 500);
        })
        .catch(err => console.error("Error al copiar:", err));
    }
  });

  // ============================
  // Imprimir etiqueta
  // ============================
  window.imprimirEtiqueta = function (productoId, ubicacionId) {
    const img = document.getElementById(`img-${productoId}-${ubicacionId}`);
    const ventana = window.open('', '_blank');

    ventana.document.write(`
      <html>
        <head>
          <title>Etiqueta</title>
          <style>
            body { margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
            img { max-width: 100%; max-height: 100%; }
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
    const enlace = document.createElement('a');
    enlace.href = img.src;
    enlace.download = `etiqueta_producto_${productoId}_${ubicacionId}.png`;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
  };

});