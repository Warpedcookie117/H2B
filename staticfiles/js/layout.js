document.addEventListener("DOMContentLoaded", function () {
  const navbar = document.getElementById("navbar");
  const sidebar = document.getElementById("sidebar");

  if (!navbar || !sidebar) {
    console.warn("Navbar o sidebar no encontrados");
    return;
  }

  // Ajuste inicial al cargar
  if (window.innerWidth >= 768) {
    sidebar.style.top = "4rem";
    sidebar.style.height = "calc(100vh - 4rem)";
  }

  let lastScrollY = window.scrollY;

  window.addEventListener("scroll", () => {
    const scrollingDown = window.scrollY > lastScrollY && window.scrollY > 100;

    // Ocultar o mostrar navbar
    navbar.classList.toggle("navbar-hidden", scrollingDown);

    // Ajustar el top y altura del sidebar en escritorio
    if (window.innerWidth >= 768) {
      const topValue = scrollingDown ? "0" : "4rem";
      sidebar.style.top = topValue;
      sidebar.style.height = `calc(100vh - ${topValue})`;
    }

    lastScrollY = window.scrollY;
  });
});


