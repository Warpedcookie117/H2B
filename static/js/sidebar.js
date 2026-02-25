document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const tab = document.getElementById("sidebar-tab");
  const icon = document.getElementById("tab-icon");

  if (!sidebar) return;

  // -----------------------------
  // 1. Restaurar estado pinned (desktop)
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
  // 2. Toggle móvil (hamburguesa)
  // -----------------------------
  if (toggle) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // -----------------------------
  // 3. Cerrar sidebar al hacer clic en un enlace (solo móvil)
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
  // 4. Botón de anclaje (desktop)
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
  // 5. Menú desplegable de Inventario (JS con transición suave)
  // -----------------------------
  const btnInv = document.getElementById("btn-inventario");
  const submenuInv = document.getElementById("submenu-inventario");
  const flechaInv = document.getElementById("flecha-inventario");

  if (btnInv && submenuInv && flechaInv) {
    btnInv.addEventListener("click", (e) => {
      e.stopPropagation();

      const abierto = submenuInv.classList.contains("submenu-open");

      if (abierto) {
        submenuInv.classList.remove("submenu-open");
        flechaInv.classList.remove("rotate-180");
      } else {
        submenuInv.classList.add("submenu-open");
        flechaInv.classList.add("rotate-180");
      }
    });
  }

  // -----------------------------
  // 6. Ajuste automático al cambiar tamaño
  // -----------------------------
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 768) {
      sidebar.classList.remove("open");
    }

    closeOnMobileClick();
  });

  console.log("✅ Sidebar listo con menú Inventario JS + transición suave");
});