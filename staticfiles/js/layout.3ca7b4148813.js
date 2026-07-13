document.addEventListener("DOMContentLoaded", function () {
  const navbar = document.getElementById("navbar");
  const sidebar = document.getElementById("sidebar");

  // Si NO hay sidebar, significa:
  // - Invitado
  // - Cliente autenticado
  // En ambos casos NO ejecutamos lógica de dashboard
  if (!sidebar) return;

  // Si hay sidebar pero no navbar (muy raro pero posible)
  if (!navbar) return;

  // Ajuste inicial al cargar (solo dashboard)
  if (window.innerWidth >= 768) {
    sidebar.style.top = "4rem";
    sidebar.style.height = "calc(100vh - 4rem)";
  }

  let lastScrollY = window.scrollY;

  window.addEventListener("scroll", () => {
    const scrollingDown = window.scrollY > lastScrollY && window.scrollY > 100;

    // Ocultar o mostrar navbar
    navbar.classList.toggle("navbar-hidden", scrollingDown);

    // Ajustar sidebar en escritorio
    if (window.innerWidth >= 768) {
      const topValue = scrollingDown ? "0" : "4rem";
      sidebar.style.top = topValue;
      sidebar.style.height = `calc(100vh - ${topValue})`;
    }

    lastScrollY = window.scrollY;
  });
});
