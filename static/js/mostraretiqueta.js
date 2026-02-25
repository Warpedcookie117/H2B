document.addEventListener("DOMContentLoaded", function () {

  // ============================
  // Mostrar / Ocultar etiqueta con animación
  // ============================
  window.mostrarEtiqueta = function (button) {
    const url = button.getAttribute("data-url");
    const productoId = button.getAttribute("data-id");
    const ubicacionId = button.getAttribute("data-ubicacion");

    const contenedor = document.getElementById(`etiqueta-${productoId}-${ubicacionId}`);
    const img = document.getElementById(`img-${productoId}-${ubicacionId}`);

    // Si ya está visible → ocultar con animación
    if (contenedor.classList.contains("show")) {
      contenedor.classList.remove("show");
      return;
    }

    // Cargar imagen del código
    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error("No se pudo cargar la etiqueta");
        return res.json();
      })
      .then(data => {
        if (data.imagen) {
          img.src = `data:image/png;base64,${data.imagen}`;
        } else {
          img.alt = "Etiqueta no disponible";
        }

        // Mostrar con animación
        contenedor.classList.add("show");
      })
      .catch(err => {
        img.alt = "Error al cargar la etiqueta";
        console.error(err);
      });
  };

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