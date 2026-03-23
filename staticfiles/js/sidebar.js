// -------------------------------------------------------------
// SIDEBAR + MODALES DINÁMICOS (CREAR CAJA + ENTRAR CAJA)
// -------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const tab = document.getElementById("sidebar-tab");
  const icon = document.getElementById("tab-icon");

  if (!sidebar) return;

  // -----------------------------
  // Restaurar estado pinned
  // -----------------------------
  const restorePinnedState = () => {
    const pinned = localStorage.getItem("sidebarPinned") === "true";

    if (pinned) {
      sidebar.classList.add("pinned");
      if (icon) {
        icon.classList.remove("fa-chevron-right");
        icon.classList.add("fa-chevron-left");
      }
    }
  };
  restorePinnedState();

  // -----------------------------
  // Toggle móvil
  // -----------------------------
  if (toggle) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // -----------------------------
  // Cerrar en móvil
  // -----------------------------
  const closeOnMobileClick = () => {
    if (window.innerWidth < 768) {
      sidebar.querySelectorAll("a").forEach((link) => {
        link.onclick = () => sidebar.classList.remove("open");
      });
    }
  };
  closeOnMobileClick();

  // -----------------------------
  // Botón de anclaje
  // -----------------------------
  if (tab && icon) {
    tab.addEventListener("click", (e) => {
      e.stopPropagation();

      const pinned = sidebar.classList.toggle("pinned");

      icon.classList.toggle("fa-chevron-left", pinned);
      icon.classList.toggle("fa-chevron-right", !pinned);

      localStorage.setItem("sidebarPinned", pinned);
    });
  }

  // -----------------------------
  // Dropdown Inventario
  // -----------------------------
  const btnInv = document.getElementById("btn-inventario");
  const submenuInv = document.getElementById("submenu-inventario");
  const flechaInv = document.getElementById("flecha-inventario");

  if (btnInv && submenuInv && flechaInv) {
    btnInv.addEventListener("click", (e) => {
      e.stopPropagation();

      const abierto = submenuInv.classList.contains("submenu-open");

      submenuInv.classList.toggle("submenu-open", !abierto);
      flechaInv.classList.toggle("rotate-180", !abierto);
    });
  }

  // -----------------------------
  // Resize
  // -----------------------------
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 768) {
      sidebar.classList.remove("open");
    }
    closeOnMobileClick();
  });

  // -----------------------------
  // Dropdown Sucursales
  // -----------------------------
  const btnSuc = document.getElementById("btn-sucursales");
  const submenuSuc = document.getElementById("submenu-sucursales");
  const flechaSuc = document.getElementById("flecha-sucursales");

  if (btnSuc && submenuSuc && flechaSuc) {
    btnSuc.addEventListener("click", (e) => {
      e.stopPropagation();

      const abierto = submenuSuc.classList.contains("submenu-open");

      submenuSuc.classList.toggle("submenu-open", !abierto);
      flechaSuc.classList.toggle("rotate-180", !abierto);
    });
  }

  // -----------------------------
  // Dropdown por sucursal
  // -----------------------------
  const sucursalBtns = document.querySelectorAll(".sucursal-btn");

  sucursalBtns.forEach((btn) => {
    const submenu = btn.parentElement.querySelector(".sucursal-submenu");
    const flecha = btn.querySelector(".sucursal-flecha");

    if (!submenu || !flecha) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();

      const abierto = submenu.classList.contains("submenu-open");

      submenu.classList.toggle("submenu-open", !abierto);
      flecha.classList.toggle("rotate-180", !abierto);
    });
  });

  // ============================================================
  // 🟣 FUNCIÓN PROFESIONAL: MENSAJE CONTEXTUAL
  // ============================================================
  function showCajaMessage(btn, msg) {
      const wrapper = btn.parentElement; // 🔥 el contenedor real
      const box = wrapper.querySelector(".msg-caja");

      if (!box) return;

      box.textContent = msg;
      box.classList.remove("hidden");

      setTimeout(() => {
          box.classList.add("hidden");
      }, 3000);
  }

  // ============================================================
  // 🟣 DELEGACIÓN: ABRIR MODAL ENTRAR CAJA
  // ============================================================
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-entrar-caja");
    if (!btn) return;

    const cajaId = btn.dataset.cajaId;
    const nombre = btn.dataset.cajaNombre;

    // 🔥 Si ya estoy en esta caja → ir directo al POS
    if (window.cajaActual && window.cajaActual == cajaId) {
      window.location.href = "/ventas/pos/";
      return;
    }

    // 🔥 Si estoy en otra caja → bloquear
    if (window.cajaActual && window.cajaActual != cajaId) {
      showCajaMessage(btn, "Debes salir de tu caja actual antes de entrar a otra.");
      return;
    }

    // Si no estoy en ninguna caja → abrir modal
    fetch(`/sucursales/modal-entrar-caja/?caja_id=${cajaId}&nombre=${encodeURIComponent(nombre)}`)
      .then((r) => r.json())
      .then((data) => {
        const modal = document.getElementById("modalEntrarCaja");
        const content = document.getElementById("modalEntrarCajaContent");

        content.innerHTML = data.html;
        modal.classList.remove("hidden");

        conectarEventosModalEntrarCaja(cajaId);
      });
  });

  // ============================================================
  // 🟣 FUNCIÓN PARA CONECTAR EVENTOS DEL MODAL ENTRAR CAJA
  // ============================================================
  function conectarEventosModalEntrarCaja(cajaId) {
    const modal = document.getElementById("modalEntrarCaja");
    const form = document.getElementById("formEntrarCaja");
    const error = document.getElementById("modalCajaError");
    const btnCancelar = document.getElementById("modalCajaCancelar");

    btnCancelar.onclick = () => modal.classList.add("hidden");

    form.onsubmit = (e) => {
      e.preventDefault();

      const formData = new FormData(form);
      formData.append("caja_id", cajaId);

      fetch("/sucursales/caja/entrar/ajax/", {
        method: "POST",
        credentials: "same-origin",
        body: formData,
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.error) {
            error.textContent = data.error;
            error.classList.remove("hidden");
            return;
          }

          window.location.href = "/ventas/pos/";
        });
    };
  }

  console.log("✅ Sidebar listo con modal dinámico de entrar caja + mensajes contextuales");
});