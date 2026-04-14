// barra_progreso.js
export function iniciarBarraProgreso(fetchPromise) {
    const container = document.getElementById("barra-progreso-container");
    const fill      = document.getElementById("barra-fill");
    const msg       = document.getElementById("barra-mensaje");

    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth", block: "center" });

    const pasos = [
        { pct: 15, txt: "Checando que no te hayas equivocado en algo... 🔍" },
        { pct: 35, txt: "Guardando los valores de atributos, papito... 💾" },
        { pct: 55, txt: "Verificando que no exista otro igual... 🕵️" },
        { pct: 72, txt: "Comparando la imagen con lo que tengo en la DB... 🖼️" },
        { pct: 88, txt: "Registrando producto en el sistema... 🚀" },
    ];

    let i = 0;
    let terminado = false;

    const intervalo = setInterval(() => {
        if (terminado || i >= pasos.length) { clearInterval(intervalo); return; }
        fill.style.width = pasos[i].pct + "%";
        msg.textContent  = pasos[i].txt;
        i++;
    }, 700);

    fetchPromise
        .then(async (resp) => {
            clearInterval(intervalo);
            terminado = true;
            const data = await resp.json();

            if (data.success) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#06D6A0";
                msg.textContent = "¡Ya chingaste, pasó el producto! 🎉";
                setTimeout(() => { window.location.href = data.redirect; }, 1200);
            } else {
                const errText = Array.isArray(data.errors)
                    ? data.errors.join(" | ")
                    : (data.errors || "Algo salió mal.");
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";
                msg.textContent = "❌ " + errText;
            }
        })
        .catch(() => {
            clearInterval(intervalo);
            terminado = true;
            fill.style.width = "100%";
            fill.style.backgroundColor = "#FF006E";
            msg.textContent = "❌ Error de conexión. Revisa tu internet.";
        });
}
