ANCHO = 30
NOMBRE_IMPRESORA = "TermicaTienda"


def imprimir_silencioso(texto):
    try:
        import win32print  # type: ignore
        printer_name = NOMBRE_IMPRESORA

        impresoras = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        if printer_name not in impresoras:
            print(f"[IMPRESION] Impresora '{printer_name}' no encontrada. Disponibles: {impresoras}")
            return False

        # 4 saltos al final para pasar la barra de corte manual.
        # Sin ESC/POS \x1D\x56: en T58W sin autocortador causa feed extra.
        datos = texto.encode("utf-8") + b"\n\n\n\n"

        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(hPrinter, 1, ("Ticket Venta", None, "RAW"))
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, datos)
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)

        print(f"[IMPRESION] Ticket enviado a '{printer_name}' correctamente.")
        return True

    except Exception as e:
        print(f"[IMPRESION] Error al imprimir: {e}")
        return False


def _c(texto):
    return texto.center(ANCHO)


def _sep(char="-"):
    return char * ANCHO


def _sep_punteado():
    return "- " * (ANCHO // 2)


def _detectar_tipo_precio(item):
    if not item.producto:
        return "MEN"
    try:
        pu = float(item.precio_unitario)
        if item.producto.precio_mayoreo and abs(pu - float(item.producto.precio_mayoreo)) < 0.01:
            return "MAY"
        if item.producto.precio_docena and abs(pu - float(item.producto.precio_docena)) < 0.01:
            return "DOC"
    except Exception:
        pass
    return "MEN"


def generar_texto_ticket(obj):

    from ventas.models import Venta, CorteCaja

    lineas = []

    # ============================================================
    # TICKET DE VENTA
    # ============================================================
    if isinstance(obj, Venta):
        venta = obj

        es_primera = not Venta.objects.filter(id__lt=venta.id).exists()

        if es_primera:
            lineas.append(_sep("*"))
            lineas.append(_c("FELICIDADES"))
            lineas.append(_c("PRIMER TICKET DE VENTA"))
            lineas.append(_c("COMERCIALIZADORA MODELO"))
            lineas.append(_c("ESTO ES HISTORIA, COMPA!"))
            lineas.append(_sep("*"))

        lineas.append(_c("COMERCIALIZADORA MODELO"))
        lineas.append(_c(f"TICKET DE VENTA: {venta.id}"))
        lineas.append(_c(f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}"))
        lineas.append(_sep())

        tipos_precio = set()

        for item in venta.detalles.all():
            producto_id = item.producto.id if item.producto else "?"
            nombre = item.nombre_snapshot or (
                item.producto.nombre if item.producto else "PRODUCTO ELIMINADO"
            )

            # Formato compacto estilo Oxxo/Walmart: #ID Nombre xCant  $precio
            etiqueta = f"#{producto_id} {nombre} x{item.cantidad}"
            precio_str = f"${item.precio_unitario:.2f}"
            # Alinear precio a la derecha dentro del ancho del ticket
            espacio = ANCHO - len(etiqueta) - len(precio_str)
            if espacio > 0:
                lineas.append(f"{etiqueta}{' ' * espacio}{precio_str}")
            else:
                # Si el nombre es muy largo, precio en la siguiente línea
                lineas.append(etiqueta)
                lineas.append(f"  {precio_str}")

            tipos_precio.add(_detectar_tipo_precio(item))

        lineas.append(_sep())

        if "MAY" in tipos_precio:
            lineas.append(_c("PRECIO MAYOREO APLICADO"))
        else:
            lineas.append(_c("PRECIO MENUDEO APLICADO"))

        lineas.append(f"Subtotal:  ${venta.subtotal:.2f}")
        lineas.append(f"Descuento: ${venta.descuento:.2f}")
        lineas.append(f"Total:     ${venta.total:.2f}")
        lineas.append(_sep())
        lineas.append(_c("METODO DE PAGO"))
        lineas.append(f"Efectivo: ${venta.pagado_efectivo:.2f}")
        lineas.append(f"Tarjeta:  ${venta.pagado_tarjeta:.2f}")
        lineas.append(f"Cambio:   ${venta.cambio:.2f}")
        lineas.append(_sep())
        lineas.append(_c("NO CAMBIOS NI DEVOLUCIONES"))
        lineas.append(_c("GRACIAS POR TU COMPRA"))

        return "\n".join(lineas)

    # ============================================================
    # TICKET DE CORTE DE CAJA
    # ============================================================
    if isinstance(obj, CorteCaja):
        corte = obj

        total_general = float(corte.total_general)

        resumen_duenos = {}

        for v in corte.ventas.all():
            for item in v.detalles.all():
                if item.producto and item.producto.dueño:
                    u = item.producto.dueño.user
                    nombre_dueno = u.first_name or u.username
                else:
                    nombre_dueno = item.nombre_snapshot or "SIN DUEÑO"

                subtotal = float(item.subtotal)

                if nombre_dueno not in resumen_duenos:
                    resumen_duenos[nombre_dueno] = {"total": 0.0, "efectivo": 0.0, "tarjeta": 0.0}

                resumen_duenos[nombre_dueno]["total"] += subtotal

                if v.metodo_pago == "efectivo":
                    resumen_duenos[nombre_dueno]["efectivo"] += subtotal
                elif v.metodo_pago == "tarjeta":
                    resumen_duenos[nombre_dueno]["tarjeta"] += subtotal
                elif v.metodo_pago == "mixto":
                    total_venta = float(v.total)
                    if total_venta > 0:
                        proporcion = subtotal / total_venta
                        efectivo_neto = float(v.pagado_efectivo) - float(v.cambio)
                        resumen_duenos[nombre_dueno]["efectivo"] += proporcion * efectivo_neto
                        resumen_duenos[nombre_dueno]["tarjeta"]  += proporcion * float(v.pagado_tarjeta)

        for d in resumen_duenos.values():
            d["total"]    = round(d["total"],    2)
            d["efectivo"] = round(d["efectivo"], 2)
            d["tarjeta"]  = round(d["tarjeta"],  2)

        total_efectivo_caja = round(sum(float(v.pagado_efectivo) - float(v.cambio) for v in corte.ventas.all()), 2)
        total_tarjeta_caja  = round(sum(float(v.pagado_tarjeta) for v in corte.ventas.all()), 2)

        lineas.append(_c("COMERCIALIZADORA MODELO"))
        lineas.append(_c("CORTE CAJA"))
        lineas.append(_c(f"Fecha: {corte.fecha.strftime('%d/%m/%Y %H:%M')}"))
        lineas.append(_c(f"Caja: {corte.caja.nombre}"))
        lineas.append(_sep())
        lineas.append(_c(f"TOTAL EN CAJA TARJETA + EFECTIVO: ${total_general:.2f}"))
        lineas.append(_sep())
        lineas.append(_c("VENTAS POR DUENO"))
        lineas.append(_sep())
        for dueno, data in resumen_duenos.items():
            lineas.append(f"  {dueno}")
            lineas.append(f"  Total vendido: ${data['total']:.2f}")
            lineas.append(f"  Efectivo:      ${data['efectivo']:.2f}")
            lineas.append(f"  Tarjeta:       ${data['tarjeta']:.2f}")
            lineas.append(_sep("-"))
        lineas.append(_sep())
        lineas.append(_c("DETALLE DEL CORTE"))
        lineas.append(_sep())
        lineas.append(f"TOTAL EFECTIVO EN CAJA: ${total_efectivo_caja:.1f}")
        lineas.append(f"TOTAL TARJETA EN CAJA:  ${total_tarjeta_caja:.1f}")
        lineas.append(_sep())
        lineas.append(_c(f"EN {corte.caja.nombre.upper()} DEBE HABER"))
        lineas.append(_c(f"${total_efectivo_caja:.2f} EN EFECTIVO"))
        lineas.append(_c("CUENTA BIEN."))
        lineas.append(_sep())
        lineas.append(_c("GRACIAS POR SU TRABAJO"))

        return "\n".join(lineas)
