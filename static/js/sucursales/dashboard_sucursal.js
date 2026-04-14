// dashboard_sucursal.js

document.addEventListener("DOMContentLoaded", () => {

  // ============================
  // ELEMENTOS
  // ============================
  const modalCrear        = document.getElementById("modalCrearCaja");
  const modalCrearContent = document.getElementById("modalCrearCajaContent");
  const modalEntrar        = document.getElementById("modalEntrarCaja");
  const modalEntrarContent = document.getElementById("modalEntrarCajaContent");
  const modalEliminar      = document.getElementById("modalEliminarCaja");
  const listaCajas         = document.getElementById("listaCajas");

  // ============================
  // MENSAJES FLOTANTES
  // ============================
  function showMsg(tipo, msg) {
    const el = document.getElementById(tipo === "ok" ? "msgSuccess" : "msgError");
    if (!el) return;
    el.innerText = msg;
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 3000);
  }

  // ============================
  // CSRF
  // ============================
  function getCSRF() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  }

  // ============================
  // MODAL CREAR CAJA
  // ============================
  window.abrirModalCrearCaja = function () {
    const url = modalCrear.dataset.urlModal;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        modalCrearContent.innerHTML = data.html;
        modalCrear.classList.remove("hidden");
        conectarEventosCrear(modalCrear.dataset.urlCrear);
      })
      .catch(() => showMsg("err", "No se pudo cargar el formulario."));
  };

  window.cerrarModalCrearCaja = function () {
    modalCrear.classList.add("hidden");
  };

  function conectarEventosCrear(urlCrear) {
    const btnGuardar  = document.getElementById("modalCrearCajaGuardar");
    const btnCancelar = document.getElementById("modalCrearCajaCancelar");
    const form        = document.getElementById("formCrearCaja");

    if (btnCancelar) {
      btnCancelar.addEventListener("click", cerrarModalCrearCaja);
    }

    if (btnGuardar && form) {
      btnGuardar.addEventListener("click", () => {
        const formData = new FormData(form);

        fetch(urlCrear, { method: "POST", body: formData })
          .then(r => r.json())
          .then(data => {
            if (data.error) {
              modalCrearContent.innerHTML = data.html;
              conectarEventosCrear(urlCrear);
              return;
            }

            // Quitar mensaje "sin cajas" si existe
            const noCajas = document.getElementById("noCajas");
            if (noCajas) noCajas.remove();

            // Agregar card de nueva caja al grid
            const div = document.createElement("div");
            div.id = `caja-card-${data.id}`;
            div.className = "border-r-4 border-b-4 border-black p-6 relative overflow-hidden hover:bg-yellow-50 transition-colors";
            div.innerHTML = `
              <div class="absolute top-0 right-0 w-8 h-8 bg-[#FFBE0B] border-l-4 border-b-4 border-black"></div>
              <p class="font-black text-lg text-gray-900 uppercase tracking-wide mb-4">${data.nombre}</p>
              <div class="flex gap-3">
                <button class="btn-90s btn-entrar-caja flex-1 bg-[#06D6A0] border-4 border-black shadow-[4px_4px_0_0_black]
                               text-black font-black text-xs uppercase tracking-widest py-2
                               flex items-center justify-center"
                        data-caja-id="${data.id}"
                        data-caja-nombre="${data.nombre}">
                  Entrar
                </button>
                ${ES_DUENO ? `
                <button onclick="confirmarEliminarCaja(${data.id}, '${data.nombre}')"
                        class="btn-90s bg-[#FF006E] border-4 border-black shadow-[4px_4px_0_0_black]
                               text-white font-black text-xs uppercase tracking-widest px-3 py-2
                               flex items-center justify-center">
                  🗑️
                </button>` : ""}
              </div>
            `;
            listaCajas.appendChild(div);

            cerrarModalCrearCaja();
            showMsg("ok", `Caja "${data.nombre}" creada.`);
          })
          .catch(() => showMsg("err", "Error al crear la caja."));
      });
    }
  }

  // ============================
  // MODAL ENTRAR CAJA (solo botones del dashboard, no del sidebar)
  // ============================
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-entrar-caja");
    if (!btn) return;

    // Solo manejar botones dentro del grid de cajas del dashboard
    if (!btn.closest("#listaCajas")) return;

    const cajaId = btn.dataset.cajaId;

    // Si ya estoy en esta misma caja → ir directo al POS
    if (window.cajaActual && window.cajaActual == cajaId) {
      window.location.href = "/ventas/pos/";
      return;
    }

    // Si estoy en otra caja → error, no permitir
    if (window.cajaActual && window.cajaActual != cajaId) {
      showMsg("err", "Debes salir de tu caja actual antes de entrar a otra.");
      return;
    }

    fetch(`/sucursales/modal-entrar-caja/?caja_id=${cajaId}&nombre=${encodeURIComponent(btn.dataset.cajaNombre)}`)
      .then(r => r.json())
      .then(data => {
        modalEntrarContent.innerHTML = data.html;
        modalEntrar.classList.remove("hidden");
        conectarEventosEntrar();
      })
      .catch(() => showMsg("err", "No se pudo cargar el modal de caja."));
  });

  window.cerrarModalEntrarCaja = function () {
    modalEntrar.classList.add("hidden");
    modalEntrarContent.innerHTML = "";
  };

  function conectarEventosEntrar() {
    const form      = document.getElementById("formEntrarCaja");
    const btnCancel = document.getElementById("modalCajaCancelar");
    const errorEl   = document.getElementById("modalCajaError");

    if (btnCancel) {
      btnCancel.addEventListener("click", cerrarModalEntrarCaja);
    }

    if (!form) return;

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (errorEl) errorEl.classList.add("hidden");

      const formData = new FormData(form);

      try {
        const r    = await fetch("/sucursales/caja/entrar/ajax/", { method: "POST", body: formData });
        const data = await r.json();

        if (data.error) {
          if (errorEl) {
            errorEl.textContent = data.error;
            errorEl.classList.remove("hidden");
          }
          return;
        }

        if (data.redirect) {
          window.location.href = data.redirect;
          return;
        }

        if (data.ok) {
          window.location.href = "/ventas/pos/";
        }
      } catch {
        showMsg("err", "Error de conexión al entrar a la caja.");
      }
    });
  }

  // ============================
  // ELIMINAR CAJA
  // ============================
  let cajaIdAEliminar = null;

  window.confirmarEliminarCaja = function (id, nombre) {
    cajaIdAEliminar = id;
    const span = document.getElementById("nombreCajaEliminar");
    if (span) span.innerText = nombre;
    modalEliminar.classList.remove("hidden");
  };

  window.cerrarModalEliminarCaja = function () {
    modalEliminar.classList.add("hidden");
    cajaIdAEliminar = null;
  };

  const btnConfirmarEliminar = document.getElementById("btnConfirmarEliminarCaja");
  if (btnConfirmarEliminar) {
    btnConfirmarEliminar.addEventListener("click", function () {
      if (!cajaIdAEliminar) return;

      fetch(`/sucursales/caja/${cajaIdAEliminar}/eliminar/`, {
        method: "POST",
        headers: { "X-CSRFToken": getCSRF() }
      })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          const card = document.getElementById(`caja-card-${cajaIdAEliminar}`);
          if (card) card.remove();

          // Si no quedan cajas, mostrar mensaje vacío
          if (listaCajas && listaCajas.querySelectorAll("[id^='caja-card-']").length === 0) {
            listaCajas.innerHTML = `
              <div id="noCajas" class="col-span-full p-8 text-center">
                <p class="text-gray-400 font-black uppercase tracking-widest text-sm">No hay cajas registradas.</p>
              </div>`;
          }

          cerrarModalEliminarCaja();
          showMsg("ok", "Caja eliminada correctamente.");
        } else {
          showMsg("err", data.error || "No se pudo eliminar.");
        }
      })
      .catch(() => showMsg("err", "Error de conexión."));
    });
  }

});