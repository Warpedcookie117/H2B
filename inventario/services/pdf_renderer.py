from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from inventario.models import Inventario, Ubicacion
from inventario.services.filtros_service import nombres_filtros
from inventario.services.reporte_service import get_datos_reporte


def generar_pdf(tipo_reporte, filtros, usuario):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_{tipo_reporte}.pdf"'

    pagesize = landscape(A4) if tipo_reporte == "movimientos" else A4
    p = canvas.Canvas(response, pagesize=pagesize)
    width, height = pagesize
    pagina = 1

    # --- Encabezado con logo y metadatos ---
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

    filtros_nombres = nombres_filtros(filtros)

    # --- Mensajes informativos según filtros ---
    p.setFont("Helvetica-Oblique", 10)
    y_info = height - 120
    mensajes = []
    if filtros_nombres.get("temporada"):
        mensajes.append(f"de la temporada {filtros_nombres['temporada']}")
    if filtros_nombres.get("ubicacion"):
        mensajes.append(f"en la ubicación {filtros_nombres['ubicacion']}")
    if filtros_nombres.get("categoria"):
        mensajes.append(f"de la categoría {filtros_nombres['categoria']}")
    if filtros_nombres.get("subcategoria"):
        mensajes.append(f"de la subcategoría {filtros_nombres['subcategoria']}")
    if filtros_nombres.get("dueño"):
        mensajes.append(f"del dueño {filtros_nombres['dueño']}")

    if mensajes:
        texto = "Estos productos son " + ", ".join(mensajes)
        p.drawString(50, y_info, texto)

    # --- Helpers internos ---
    y = height - 190
    def nueva_pagina():
        nonlocal y, pagina
        p.setFont("Helvetica", 9)
        p.drawRightString(width - 30, 20, f"Página {pagina}")
        p.showPage()
        pagina += 1
        y = height - 100

    def dibujar_fila(celdas, negrita=False):
        nonlocal y
        if y < 80:
            nueva_pagina()
        p.setFont("Helvetica-Bold" if negrita else "Helvetica", 9)
        x = 50
        ancho_disponible = width - 100
        ancho_columna = ancho_disponible / len(celdas)
        for texto in celdas:
            p.rect(x, y, ancho_columna, 15, stroke=1, fill=0)
            p.drawString(x + 2, y + 3, str(texto))
            x += ancho_columna
        y -= 15

    # --- Datos del reporte ---
    datos = get_datos_reporte(
        tipo_reporte,
        categoria_id=filtros.get("categoria"),
        subcategoria_id=filtros.get("subcategoria"),
        temporada_id=filtros.get("temporada"),
        ubicacion_id=filtros.get("ubicacion"),
        dueño_id=filtros.get("dueño"),
        movimiento_tipo=filtros.get("movimiento")
    )

    # --- Renderizado según tipo ---
    if tipo_reporte in ["general", "movimientos"]:
        columnas = ["Producto"]
        if tipo_reporte == "movimientos" and not filtros.get("movimiento"):
            columnas.append("Tipo")
        if not filtros.get("dueño"):
            columnas.append("Dueño")
        if not filtros.get("categoria"):
            columnas.append("Categoría")
        if not filtros.get("subcategoria"):
            columnas.append("Subcategoría")
        if not filtros.get("temporada"):
            columnas.append("Temporada")
        if not filtros.get("ubicacion") and tipo_reporte == "general":
            columnas.append("Ubicación")

        columnas.append("Cantidad")
        if tipo_reporte == "movimientos":
            columnas += ["Origen", "Destino", "Fecha"]

        dibujar_fila(columnas, negrita=True)

        for item in datos:
            fila = [item.get("producto_nombre", "N/A")]
            if tipo_reporte == "movimientos" and not filtros.get("movimiento"):
                fila.append(item.get("tipo", "N/A"))
            if not filtros.get("dueño"):
                fila.append(item.get("dueño_nombre", "N/A"))
            if not filtros.get("categoria"):
                fila.append(item.get("categoria_nombre", "N/A"))
            if not filtros.get("subcategoria"):
                fila.append(item.get("subcategoria_nombre", "N/A"))
            if not filtros.get("temporada"):
                fila.append(item.get("temporada_nombres", "N/A"))
            if not filtros.get("ubicacion") and tipo_reporte == "general":
                fila.append(item.get("ubicacion_nombre", "N/A"))

            # Cantidad
            if tipo_reporte == "general":
                fila.append(item.get("total", 0))
            else:  # movimientos
                fila.append(item.get("cantidad", 0))

            if tipo_reporte == "movimientos":
                fecha = item.get("fecha")
                fila += [
                    item.get("origen_nombre", "-"),
                    item.get("destino_nombre", "-"),
                    fecha.strftime("%d/%m/%Y %H:%M") if isinstance(fecha, datetime) else "-"
                ]
            dibujar_fila(fila)

    p.save()
    return response

def exportar_criticos_pdf(usuario, ubicacion_id=None):
    criticos = Inventario.objects.filter(cantidad_actual__lte=100)
    if ubicacion_id:
        criticos = criticos.filter(ubicacion_id=ubicacion_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="productos_bajo_stock.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    pagina = 1
    y = height - 100

    # --- Encabezado con logo ---
    logo_path = "static/img/logotienda.png"
    try:
        p.drawImage(logo_path, 50, height - 80, width=60, height=60,
                    preserveAspectRatio=True, mask='auto')
    except:
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

    # --- Tabla de críticos ---
    y = height - 160
    def nueva_pagina():
        nonlocal y, pagina
        p.setFont("Helvetica", 9)
        p.drawRightString(width - 30, 20, f"Página {pagina}")
        p.showPage()
        pagina += 1
        y = height - 100

    def dibujar_fila(celdas, anchos, negrita=False):
        nonlocal y
        if y < 80:
            nueva_pagina()
        p.setFont("Helvetica-Bold" if negrita else "Helvetica", 9)
        x = 50
        for texto, ancho in zip(celdas, anchos):
            p.rect(x, y, ancho, 15, stroke=1, fill=0)
            p.drawString(x + 2, y + 3, str(texto))
            x += ancho
        y -= 15

    # Encabezados
    dibujar_fila(["Producto", "Stock actual", "Ubicación"], [200, 100, 200], negrita=True)

    # Filas
    for inv in criticos:
        dibujar_fila([inv.producto.nombre, inv.cantidad_actual, inv.ubicacion.nombre],
                     [200, 100, 200])

    p.showPage()
    p.save()
    return response
