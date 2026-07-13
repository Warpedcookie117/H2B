document.addEventListener("DOMContentLoaded", () => {
  // Encuentra todos los formularios
  const forms = document.querySelectorAll("form");

  // Función para aplicar estilos Bootstrap a campos dinámicos
  function aplicarEstiloFormControl(contenedorId) {
    const contenedor = document.getElementById(contenedorId);
    if (!contenedor) return;

    const campos = contenedor.querySelectorAll("input, select, textarea");
    campos.forEach((campo) => {
      campo.classList.add("form-control");
    });
  }

  forms.forEach((form) => {
    const btn = form.querySelector(".btn-submit");
    const btnText = btn?.querySelector("span");
    const spinner = form.querySelector(".spinner");

    // Elementos condicionales (solo si existen en el formulario actual)
    const slideSwitch = form.querySelector("#slide-switch");
    const padreSelect = form.querySelector("#campo-padre");

    form.addEventListener("submit", (e) => {
      // Aplica estilos a los atributos dinámicos antes de enviar
      aplicarEstiloFormControl("atributos-container");

      // Validación solo si el formulario tiene el switch
      if (slideSwitch && slideSwitch.checked && (!padreSelect || !padreSelect.value)) {
        e.preventDefault();
        alert("Selecciona una categoría padre antes de registrar una subcategoría.");
        return;
      }

      // Animación del botón (funciona en todos los formularios)
      if (btn) btn.disabled = true;
      if (btnText) btnText.textContent = "Registrando...";
      if (spinner) spinner.classList.remove("hidden");
    });
  });

  // También aplica estilos cuando se selecciona una subcategoría (por si los atributos se insertan en ese momento)
  const subSelect = document.getElementById("id_subcategoria");
  if (subSelect) {
    subSelect.addEventListener("change", () => {
      setTimeout(() => {
        aplicarEstiloFormControl("atributos-container");
      }, 50); // pequeño delay para esperar a que los campos se inserten
    });
  }
});
