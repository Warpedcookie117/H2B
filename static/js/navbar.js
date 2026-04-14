document.addEventListener("DOMContentLoaded", function () {

  const toggle  = document.getElementById("menu-toggle");
  const menu    = document.getElementById("menu");
  const navbar  = document.getElementById("navbar");

  console.log("[navbar] toggle:", toggle);
  console.log("[navbar] menu:", menu);
  console.log("[navbar] navbar:", navbar);

  let menuAbierto   = false;
  let lastScrollTop = 0;
  let ticking       = false;
  let ignoreScroll  = false;

  // ABRIR MENÚ MOBILE
  function abrirMenu() {
    menu.classList.remove("hidden");
    // Forzar reflow para que la transición arranque
    void menu.offsetHeight;
    menu.classList.remove("opacity-0", "pointer-events-none", "-translate-y-4");
    menu.classList.add("opacity-100", "pointer-events-auto", "translate-y-0");

    // Animar cada link con stagger
    const links = menu.querySelectorAll("a, button");
    links.forEach((link, i) => {
      link.style.opacity = "0";
      link.style.transform = "translateX(-12px)";
      link.style.transition = `opacity 0.2s ease ${i * 40}ms, transform 0.2s ease ${i * 40}ms`;
      setTimeout(() => {
        link.style.opacity = "1";
        link.style.transform = "translateX(0)";
      }, 10);
    });
  }

  // CERRAR MENÚ MOBILE
  function cerrarMenu() {
    const links = menu.querySelectorAll("a, button");
    links.forEach((link, i) => {
      const reverseI = links.length - 1 - i;
      link.style.transition = `opacity 0.15s ease ${reverseI * 25}ms, transform 0.15s ease ${reverseI * 25}ms`;
      link.style.opacity = "0";
      link.style.transform = "translateX(-8px)";
    });

    setTimeout(() => {
      menu.classList.remove("opacity-100", "pointer-events-auto", "translate-y-0");
      menu.classList.add("opacity-0", "pointer-events-none", "-translate-y-4");
      setTimeout(() => {
        if (!menuAbierto) menu.classList.add("hidden");
      }, 250);
    }, links.length * 25 + 50);
  }

  function toggleMenu(forceClose = false) {
    ignoreScroll = true;
    setTimeout(() => ignoreScroll = false, 400);

    menuAbierto = forceClose ? false : !menuAbierto;

    if (menuAbierto) {
      abrirMenu();
      navbar.classList.remove("-translate-y-full");
    } else {
      cerrarMenu();
    }

    // Animar el ícono hamburguesa
    animarHamburguesa(menuAbierto);
  }

  // ANIMACIÓN HAMBURGUESA → X
  function animarHamburguesa(abierto) {
    const svg = toggle.querySelector("svg");
    if (!svg) return;
    svg.style.transition = "transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)";
    svg.style.transform = abierto ? "rotate(90deg) scale(1.15)" : "rotate(0deg) scale(1)";
  }

  // CLICK EN HAMBURGUESA
  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    console.log("[navbar] click hamburguesa, menuAbierto antes:", menuAbierto);
    console.log("[navbar] menu classes antes:", menu.className);
    toggleMenu();
    console.log("[navbar] menu classes despues:", menu.className);
  });

  // CLICK EN LINKS DEL MENÚ
  menu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMenu(true);
    });
  });

  // CLICK FUERA DEL NAVBAR
  document.addEventListener("click", (e) => {
    if (menuAbierto && !navbar.contains(e.target)) {
      toggleMenu(true);
    }
  });

  // SCROLL SUAVE — navbar fluido con easing
  window.addEventListener("scroll", function () {
    if (menuAbierto || ignoreScroll) return;

    const currentScroll = window.pageYOffset || document.documentElement.scrollTop;

    if (!ticking) {
      window.requestAnimationFrame(() => {
        const bajando  = currentScroll > lastScrollTop + 5;
        const subiendo = currentScroll < lastScrollTop - 5;

        if (bajando && currentScroll > 60) {
          navbar.style.transition = "transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)";
          navbar.classList.add("-translate-y-full");
        } else if (subiendo) {
          navbar.style.transition = "transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)";
          navbar.classList.remove("-translate-y-full");
        }

        lastScrollTop = currentScroll <= 0 ? 0 : currentScroll;
        ticking = false;
      });

      ticking = true;
    }
  });

  // DROPDOWN PERFIL
  const profileBtn      = document.getElementById("profileMenuBtn");
  const profileDropdown = document.getElementById("profileDropdown");

  if (profileBtn && profileDropdown) {
    profileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const abriendo = profileDropdown.classList.contains("hidden");
      profileDropdown.classList.toggle("hidden");

      if (abriendo) {
        profileDropdown.style.opacity = "0";
        profileDropdown.style.transform = "translateY(-6px) scale(0.97)";
        profileDropdown.style.transition = "opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)";
        void profileDropdown.offsetHeight;
        profileDropdown.style.opacity = "1";
        profileDropdown.style.transform = "translateY(0) scale(1)";
      }
    });

    document.addEventListener("click", (e) => {
      if (
        !profileDropdown.classList.contains("hidden") &&
        !profileDropdown.contains(e.target) &&
        !profileBtn.contains(e.target)
      ) {
        profileDropdown.style.opacity = "0";
        profileDropdown.style.transform = "translateY(-4px) scale(0.97)";
        setTimeout(() => profileDropdown.classList.add("hidden"), 150);
      }
    });
  }

});