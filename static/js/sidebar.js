document.addEventListener("DOMContentLoaded", () => {

  const sidebar = document.getElementById("sidebar");
  const toggle  = document.getElementById("sidebar-toggle");
  const tab     = document.getElementById("sidebar-tab");

  if (!sidebar) return;

  // ============================================================
  // AJUSTAR SIDEBAR AL NAVBAR Y FOOTER DINÁMICAMENTE
  // ============================================================
  function ajustarSidebar() {
    if (window.innerWidth < 768) return; // móvil lo maneja el CSS

    const navbar  = document.getElementById("navbar");
    const footer  = document.querySelector("footer");

    const navH      = navbar ? navbar.getBoundingClientRect().height : 64;
    const scrollY   = window.scrollY;

    // Top del sidebar = fondo del navbar visible
    const topOffset = Math.max(0, navH - scrollY);

    // Bottom del sidebar = top del footer visible (o fondo de ventana)
    let bottomOffset = window.innerHeight;
    if (footer) {
      const footerRect = footer.getBoundingClientRect();
      if (footerRect.top < window.innerHeight) {
        bottomOffset = footerRect.top;
      }
    }

    const sidebarHeight = Math.max(0, bottomOffset - topOffset);

    sidebar.style.top    = topOffset + "px";
    sidebar.style.height = sidebarHeight + "px";

    // Mover pestaña de anclaje también
    if (tab) {
      tab.style.top = (topOffset + 12) + "px";
    }
  }

  ajustarSidebar();
  window.addEventListener("scroll", ajustarSidebar);
  window.addEventListener("resize", ajustarSidebar);

  // ============================================================
  // ESTADO PINNED
  // ============================================================
  const isPinned = () => localStorage.getItem("sidebarPinned") === "true";

  const applyPinned = (pinned) => {
    sidebar.classList.toggle("pinned", pinned);
    localStorage.setItem("sidebarPinned", pinned);
    // Mover pestaña según estado
    if (tab) {
      tab.style.left = pinned ? "16rem" : "4rem";
    }
    // Empujar contenido solo en desktop
    if (window.innerWidth >= 768) {
      const main = document.getElementById("main-content");
      if (main) {
        // Pinned → empujar a 16rem; no pinned → el CSS md:ml-16 (4rem) toma el control
        main.style.marginLeft = pinned ? "16rem" : "";
      }
    }
  };

  applyPinned(isPinned());

  // ============================================================
  // PESTAÑA DE ANCLAJE
  // ============================================================
  if (tab) {
    tab.addEventListener("click", (e) => {
      e.stopPropagation();
      applyPinned(!isPinned());
    });
  }

  // Mover pestaña también en hover (sin pinned)
  sidebar.addEventListener("mouseenter", () => {
    if (!isPinned() && tab) tab.style.left = "16rem";
  });
  sidebar.addEventListener("mouseleave", () => {
    if (!isPinned() && tab) tab.style.left = "4rem";
  });

  // ============================================================
  // HAMBURGUESA MÓVIL
  // ============================================================
  if (toggle) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // Cerrar móvil al hacer clic en un link
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth < 768) {
        sidebar.classList.remove("open");
      }
    });
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth >= 768) {
      sidebar.classList.remove("open");
      // Re-aplicar margen correcto al volver a desktop
      applyPinned(isPinned());
    } else {
      // En móvil, el sidebar es overlay → sin margen
      const main = document.getElementById("main-content");
      if (main) main.style.marginLeft = "";
    }
  });

  // ============================================================
  // HELPER SUBMENÚ
  // ============================================================
  function toggleSubmenu(btn, submenu, flecha) {
    if (!btn || !submenu || !flecha) return;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const abierto = submenu.classList.contains("submenu-open");
      submenu.classList.toggle("submenu-open", !abierto);
      flecha.classList.toggle("rotate-180", !abierto);
    });
  }

  // ============================================================
  // SUBMENÚ ALMACENES
  // ============================================================
  toggleSubmenu(
    document.getElementById("btn-inventario"),
    document.getElementById("submenu-inventario"),
    document.getElementById("flecha-inventario")
  );

  // ============================================================
  // SUBMENÚ SUCURSALES
  // ============================================================
  toggleSubmenu(
    document.getElementById("btn-sucursales"),
    document.getElementById("submenu-sucursales"),
    document.getElementById("flecha-sucursales")
  );

  // ============================================================
  // SUBMENÚ POR SUCURSAL
  // ============================================================
  document.querySelectorAll(".sucursal-btn").forEach((btn) => {
    const submenu = btn.parentElement.querySelector(".sucursal-submenu");
    const flecha  = btn.querySelector(".sucursal-flecha");
    toggleSubmenu(btn, submenu, flecha);
  });

  // ============================================================
  // MENSAJE CONTEXTUAL CAJA
  // ============================================================
  function showCajaMessage(btn, msg) {
    const box = btn.parentElement.querySelector(".msg-caja");
    if (!box) return;
    box.textContent = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 3000);
  }

  // ============================================================
  // MODAL ENTRAR CAJA
  // ============================================================
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-entrar-caja");
    if (!btn) return;

    const cajaId = btn.dataset.cajaId;
    const nombre = btn.dataset.cajaNombre;

    if (window.cajaActual && window.cajaActual == cajaId) {
      window.location.href = "/ventas/pos/";
      return;
    }

    if (window.cajaActual && window.cajaActual != cajaId) {
      showCajaMessage(btn, "Debes salir de tu caja actual antes de entrar a otra.");
      return;
    }

    fetch(`/sucursales/modal-entrar-caja/?caja_id=${cajaId}&nombre=${encodeURIComponent(nombre)}`)
      .then((r) => r.json())
      .then((data) => {
        const modal   = document.getElementById("modalEntrarCaja");
        const content = document.getElementById("modalEntrarCajaContent");
        content.innerHTML = data.html;
        modal.classList.remove("hidden");
        conectarEventosModal(cajaId);
      });
  });

  function conectarEventosModal(cajaId) {
    const modal     = document.getElementById("modalEntrarCaja");
    const form      = document.getElementById("formEntrarCaja");
    const error     = document.getElementById("modalCajaError");
    const btnCancel = document.getElementById("modalCajaCancelar");

    if (btnCancel) btnCancel.onclick = () => modal.classList.add("hidden");

    if (form) {
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
              if (error) {
                error.textContent = data.error;
                error.classList.remove("hidden");
              }
              return;
            }
            if (data.redirect) {
              window.location.href = data.redirect;
              return;
            }
            window.location.href = "/ventas/pos/";
          });
      };
    }
  }

});