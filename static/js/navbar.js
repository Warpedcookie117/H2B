document.addEventListener("DOMContentLoaded", function () {
  // Menú hamburguesa (móvil)
  const toggle = document.getElementById("menu-toggle");
  const menu = document.getElementById("menu");

  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      menu.classList.toggle("opacity-0");
      menu.classList.toggle("pointer-events-none");
      menu.classList.toggle("translate-y-0");
      menu.classList.toggle("-translate-y-4");
    });

    const menuLinks = menu.querySelectorAll("a");
    menuLinks.forEach((link) => {
      link.addEventListener("click", () => {
        menu.classList.add("opacity-0");
        menu.classList.add("pointer-events-none");
        menu.classList.remove("translate-y-0");
        menu.classList.add("-translate-y-4");
      });
    });
  }

  // Ocultar navbar al hacer scroll hacia abajo
  const navbar = document.getElementById("navbar");
  let lastScrollTop = 0;

  window.addEventListener("scroll", function () {
    const currentScroll = window.pageYOffset || document.documentElement.scrollTop;

    if (currentScroll > lastScrollTop) {
      navbar.classList.add("transform", "-translate-y-full");
    } else {
      navbar.classList.remove("-translate-y-full");
    }

    lastScrollTop = currentScroll <= 0 ? 0 : currentScroll;
  });

  // Dropdown de perfil (desktop)
  const profileBtn = document.getElementById("profileMenuBtn");
  const profileDropdown = document.getElementById("profileDropdown");

  if (profileBtn && profileDropdown) {
    profileBtn.addEventListener("click", (e) => {
      e.stopPropagation(); // evita que el clic se propague y cierre el menú
      profileDropdown.classList.toggle("hidden");
    });

    document.addEventListener("click", (e) => {
      if (
        !profileDropdown.classList.contains("hidden") &&
        !profileDropdown.contains(e.target) &&
        !profileBtn.contains(e.target)
      ) {
        profileDropdown.classList.add("hidden");
      }
    });
  }
});
