from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from inventario.models import Inventario, Ubicacion
from inventario.services.filtros_service import nombres_filtros
from inventario.services.reporte_service import get_datos_reporte


# Pesos relativos por columna para repartir el ancho proporcionalmente
_PESOS = {
    "Producto":      3.0,
    "Dueño":         1.5,
    "Categoría":     2.0,
    "Subcategoría":  2.0,
    "Temporada":     1.5,
    "Ubicación":     2.5,
    "Cantidad":      1.0,
    "Total movido":  1.0,
    "Tipo":          1.5,
    "Motivo":        2.0,
    "Origen":        2.0,
    "Destino":       2.0,
    "Fecha":         2.0,
}


def _anchos_columnas(columnas, ancho_disponible):
    total = sum(_PESOS.get(c, 1.5) for c in columnas)
    return [(_PESOS.get(c, 1.5) / total) * ancho_disponible for c in columnas]


def _truncar(texto, ancho_max, fuente, tamano):
    texto = str(texto) if texto is not None else "—"
    espacio = ancho_max - 4
    if stringWidth(texto, fuente, tamano) <= espacio:
        return texto
    while texto and stringWidth(texto + "…", fuente, tamano) > espacio:
        texto = texto[:-1]
    return texto + "…"


def _encabezado(p, width, height, usuario):
    logo_path = "static/img/logotienda.png"
    try:
        p.drawImage(logo_path, 50, height - 80, width=60, height=60,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    p.setFont("Helvetica-Bold", 16)
    p.drawRightString(width - 50, height - 50, "Comercializadora Modelo")
    p.setFont("Helvetica", 10)
    p.drawRightString(width - 50, height - 70, f"Reporte generado por: {usuario}")
    p.drawRightString(width - 50, height - 85, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


def _mensaje_filtros(p, filtros_nombres, filtros_raw, y_inicio):
    """Dibuja cada filtro activo en su propia línea. Retorna la y final."""
    lineas = []
    if filtros_nombres.get("categoria"):
        lineas.append(("Categoría", filtros_nombres["categoria"]))
    if filtros_nombres.get("subcategoria"):
        lineas.append(("Subcategoría", filtros_nombres["subcategoria"]))
    if filtros_nombres.get("ubicacion"):
        lineas.append(("Ubicación", filtros_nombres["ubicacion"]))
    if filtros_nombres.get("temporada"):
        lineas.append(("Temporada", filtros_nombres["temporada"]))
    if filtros_nombres.get("dueño"):
        lineas.append(("Dueño", filtros_nombres["dueño"]))
    if filtros_raw.get("movimiento"):
        lineas.append(("Tipo de movimiento", filtros_raw["movimiento"].capitalize()))

    if not lineas:
        return y_inicio

    y = y_inicio
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "Filtros aplicados:")
    y -= 13
    p.setFont("Helvetica", 9)
    for etiqueta, valor in lineas:
        p.drawString(58, y, f"• {etiqueta}: {valor}")
        y -= 12
    return y - 6


def generar_pdf(tipo_reporte, filtros, usuario):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_{tipo_reporte}.pdf"'

    pagesize = landscape(A4) if tipo_reporte == "movimientos" else A4
    p = canvas.Canvas(response, pagesize=pagesize)
    width, height = pagesize
    pagina = [1]

    _encabezado(p, width, height, usuario)
    y_filtros = _mensaje_filtros(p, nombres_filtros(filtros), filtros, height - 115)

    ancho_disponible = width - 100
    state = {"y": y_filtros - 10}

    def nueva_pagina():
        p.setFont("Helvetica", 9)
        p.drawRightString(width - 30, 20, f"Página {pagina[0]}")
        p.showPage()
        pagina[0] += 1
        state["y"] = height - 80

    def dibujar_fila(celdas, anchos, negrita=False):
        if state["y"] < 80:
            nueva_pagina()
        fuente = "Helvetica-Bold" if negrita else "Helvetica"
        p.setFont(fuente, 9)
        x = 50
        for texto, ancho in zip(celdas, anchos):
            p.rect(x, state["y"], ancho, 15, stroke=1, fill=0)
            p.drawString(x + 2, state["y"] + 3, _truncar(texto, ancho, fuente, 9))
            x += ancho
        state["y"] -= 15

    datos = get_datos_reporte(
        tipo_reporte,
        categoria_id=filtros.get("categoria"),
        subcategoria_id=filtros.get("subcategoria"),
        temporada_id=filtros.get("temporada"),
        ubicacion_id=filtros.get("ubicacion"),
        dueño_id=filtros.get("dueño"),
        movimiento_tipo=filtros.get("movimiento"),
    )

    # ── INVENTARIO GENERAL ──────────────────────────────────────
    if tipo_reporte == "general":
        columnas = ["Producto"]
        if not filtros.get("dueño"):        columnas.append("Dueño")
        if not filtros.get("categoria"):    columnas.append("Categoría")
        if not filtros.get("subcategoria"): columnas.append("Subcategoría")
        if not filtros.get("temporada"):    columnas.append("Temporada")
        if not filtros.get("ubicacion"):    columnas.append("Ubicación")
        columnas.append("Cantidad")

        anchos = _anchos_columnas(columnas, ancho_disponible)
        dibujar_fila(columnas, anchos, negrita=True)

        for item in datos:
            fila = [item.get("producto_nombre", "—")]
            if not filtros.get("dueño"):        fila.append(item.get("dueño_nombre", "—"))
            if not filtros.get("categoria"):    fila.append(item.get("categoria_nombre", "—"))
            if not filtros.get("subcategoria"): fila.append(item.get("subcategoria_nombre", "—"))
            if not filtros.get("temporada"):    fila.append(item.get("temporada_nombres", "—"))
            if not filtros.get("ubicacion"):    fila.append(item.get("ubicacion_nombre", "—"))
            fila.append(item.get("total", 0))
            dibujar_fila(fila, anchos)

    # ── MOVIMIENTOS ─────────────────────────────────────────────
    elif tipo_reporte == "movimientos":
        columnas = ["Producto"]
        if not filtros.get("movimiento"):   columnas.append("Tipo")
        if not filtros.get("dueño"):        columnas.append("Dueño")
        if not filtros.get("categoria"):    columnas.append("Categoría")
        if not filtros.get("subcategoria"): columnas.append("Subcategoría")
        if not filtros.get("temporada"):    columnas.append("Temporada")
        columnas += ["Cantidad", "Origen", "Destino", "Fecha"]

        anchos = _anchos_columnas(columnas, ancho_disponible)
        dibujar_fila(columnas, anchos, negrita=True)

        for item in datos:
            fila = [item.get("producto_nombre", "—")]
            if not filtros.get("movimiento"):   fila.append(item.get("tipo", "—"))
            if not filtros.get("dueño"):        fila.append(item.get("dueño_nombre", "—"))
            if not filtros.get("categoria"):    fila.append(item.get("categoria_nombre", "—"))
            if not filtros.get("subcategoria"): fila.append(item.get("subcategoria_nombre", "—"))
            if not filtros.get("temporada"):    fila.append(item.get("temporada_nombres", "—"))
            fecha = item.get("fecha")
            fila += [
                item.get("cantidad", 0),
                item.get("origen_nombre", "—"),
                item.get("destino_nombre", "—"),
                fecha.strftime("%d/%m/%Y %H:%M") if isinstance(fecha, datetime) else "—",
            ]
            dibujar_fila(fila, anchos)

    # ── RESUMEN DE MOVIMIENTOS ──────────────────────────────────
    elif tipo_reporte == "resumen_movimientos":
        columnas = ["Tipo", "Producto"]
        if not filtros.get("dueño"):        columnas.append("Dueño")
        if not filtros.get("categoria"):    columnas.append("Categoría")
        if not filtros.get("subcategoria"): columnas.append("Subcategoría")
        if not filtros.get("temporada"):    columnas.append("Temporada")
        columnas.append("Total movido")

        anchos = _anchos_columnas(columnas, ancho_disponible)
        dibujar_fila(columnas, anchos, negrita=True)

        for item in datos:
            fila = [item.get("tipo", "—"), item.get("producto__nombre", "—")]
            if not filtros.get("dueño"):        fila.append(item.get("producto__dueño__user__username", "—"))
            if not filtros.get("categoria"):    fila.append(item.get("producto__categoria_padre__nombre", "—"))
            if not filtros.get("subcategoria"): fila.append(item.get("producto__categoria__nombre", "—"))
            if not filtros.get("temporada"):    fila.append(item.get("temporada_nombres", "—"))
            fila.append(item.get("total", 0))
            dibujar_fila(fila, anchos)

    p.setFont("Helvetica", 9)
    p.drawRightString(width - 30, 20, f"Página {pagina[0]}")
    p.save()
    return response


def exportar_criticos_pdf(usuario, ubicacion_id=None):
    criticos = Inventario.objects.filter(cantidad_actual__lte=100).select_related("producto", "ubicacion")
    if ubicacion_id:
        criticos = criticos.filter(ubicacion_id=ubicacion_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="productos_bajo_stock.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    pagina = [1]

    logo_path = "static/img/logotienda.png"
    try:
        p.drawImage(logo_path, 50, height - 80, width=60, height=60,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    p.setFont("Helvetica-Bold", 16)
    p.drawRightString(width - 50, height - 50, "Comercializadora Modelo")
    p.setFont("Helvetica", 10)
    p.drawRightString(width - 50, height - 70, f"Reporte generado por: {usuario}")
    p.drawRightString(width - 50, height - 85, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if ubicacion_id:
        ubicacion = Ubicacion.objects.filter(id=ubicacion_id).first()
        if ubicacion:
            p.drawRightString(width - 50, height - 100, f"Ubicación: {ubicacion.nombre}")

    ANCHOS = [200, 100, 200]
    state = {"y": height - 160}

    def nueva_pagina():
        p.setFont("Helvetica", 9)
        p.drawRightString(width - 30, 20, f"Página {pagina[0]}")
        p.showPage()
        pagina[0] += 1
        state["y"] = height - 80

    def dibujar_fila(celdas, negrita=False):
        if state["y"] < 80:
            nueva_pagina()
        fuente = "Helvetica-Bold" if negrita else "Helvetica"
        p.setFont(fuente, 9)
        x = 50
        for texto, ancho in zip(celdas, ANCHOS):
            p.rect(x, state["y"], ancho, 15, stroke=1, fill=0)
            p.drawString(x + 2, state["y"] + 3, _truncar(texto, ancho, fuente, 9))
            x += ancho
        state["y"] -= 15

    dibujar_fila(["Producto", "Stock actual", "Ubicación"], negrita=True)
    for inv in criticos:
        dibujar_fila([inv.producto.nombre, inv.cantidad_actual, inv.ubicacion.nombre])

    p.setFont("Helvetica", 9)
    p.drawRightString(width - 30, 20, f"Página {pagina[0]}")
    p.save()
    return response
