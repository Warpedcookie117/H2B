from django.utils import timezone

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

    from ventas.models import Venta, CorteCaja, ConfigTicket

    cfg = ConfigTicket.get()
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
            lineas.append(_c(cfg.nombre_empresa))
            lineas.append(_c("ESTO ES HISTORIA, COMPA!"))
            lineas.append(_sep("*"))

        lineas.append(_c(cfg.nombre_empresa))
        if cfg.telefono:
            lineas.append(_c(cfg.telefono))
        if cfg.direccion:
            lineas.append(_c(cfg.direccion))
        lineas.append(_c(f"TICKET DE VENTA: {venta.id}"))
        lineas.append(_c(f"Fecha: {timezone.localtime(venta.fecha).strftime('%d/%m/%Y %H:%M')}"))
        lineas.append(_sep())

        tipos_precio = set()

        for item in venta.detalles.all():
            es_regalo = (item.atributos_snapshot or {}).get("tipo") == "regalo"
            producto_id = item.producto.id if item.producto else "?"
            nombre = item.nombre_snapshot or (
                item.producto.nombre if item.producto else "PRODUCTO ELIMINADO"
            )

            if cfg.mostrar_id_producto:
                prefijo = f"#{producto_id} "
            else:
                prefijo = ""

            if es_regalo:
                etiqueta   = f"{prefijo}{nombre} x{item.cantidad}"
                precio_str = "$0.00 *PROMO*"
            else:
                etiqueta   = f"{prefijo}{nombre} x{item.cantidad}"
                precio_str = f"${item.precio_unitario:.2f}"

            espacio = ANCHO - len(etiqueta) - len(precio_str)
            if espacio > 0:
                lineas.append(f"{etiqueta}{' ' * espacio}{precio_str}")
            else:
                lineas.append(etiqueta)
                lineas.append(f"  {precio_str}")

            if es_regalo:
                promo_nombre = (item.atributos_snapshot or {}).get("promo", "")
                if promo_nombre:
                    lineas.append(f"  --> {promo_nombre}")

            tipos_precio.add(_detectar_tipo_precio(item))

        lineas.append(_sep())

        if cfg.mostrar_tipo_precio:
            if "MAY" in tipos_precio:
                lineas.append(_c(cfg.texto_mayoreo))
            else:
                lineas.append(_c(cfg.texto_menudeo))

        lineas.append(f"Subtotal:  ${venta.subtotal:.2f}")
        lineas.append(f"Descuento: ${venta.descuento:.2f}")
        lineas.append(f"Total:     ${venta.total:.2f}")
        lineas.append(_sep())
        lineas.append(_c("METODO DE PAGO"))
        lineas.append(f"Efectivo: ${venta.pagado_efectivo:.2f}")
        lineas.append(f"Tarjeta:  ${venta.pagado_tarjeta:.2f}")
        lineas.append(f"Cambio:   ${venta.cambio:.2f}")
        lineas.append(_sep())
        if cfg.mensaje_pie:
            lineas.append(_c(cfg.mensaje_pie))
        if cfg.mensaje_agradecimiento:
            lineas.append(_c(cfg.mensaje_agradecimiento))

        return "\n".join(lineas)

    # ============================================================
    # TICKET DE CORTE DE CAJA
    # ============================================================
    if isinstance(obj, CorteCaja):
        # Import local: pos_service importa este módulo; así no hay ciclos.
        from ventas.services.reparto import desglose_y_deudas, totales_caja, ventas_para_desglose

        corte = obj

        total_general = float(corte.total_general)

        # Mismo desglose que la vista web del corte (reparto.py): montos ya
        # con descuento, regalos fuera y servicios dentro de la fila de la
        # responsable de servicios. Σ filas == totales de la caja, exacto.
        # Una sola pasada: el queryset de ventas_para_desglose se consume al iterar.
        # Las deudas entre duenas NO van en el corte (son sensibles: solo en
        # el dashboard de cada duena); se descarta el segundo valor.
        filas_duenos, _ = desglose_y_deudas(ventas_para_desglose(corte.ventas.all()))
        tot = totales_caja(corte.ventas.all())
        total_efectivo_caja = tot["efectivo"]
        total_tarjeta_caja = tot["tarjeta"]

        # La caja pudo haberse borrado (FK SET_NULL): queda el snapshot.
        nombre_caja = corte.caja.nombre if corte.caja else (corte.caja_nombre or "Caja eliminada")

        lineas.append(_c(cfg.nombre_empresa))
        lineas.append(_c("CORTE CAJA"))
        lineas.append(_c(f"Fecha: {timezone.localtime(corte.fecha).strftime('%d/%m/%Y %H:%M')}"))
        lineas.append(_c(f"Caja: {nombre_caja}"))
        lineas.append(_sep())
        # En una sola línea no cabía en ANCHO (se cortaba en la térmica).
        lineas.append(_c("TOTAL EN CAJA"))
        lineas.append(_c("TARJETA + EFECTIVO"))
        lineas.append(_c(f"${total_general:.2f}"))
        lineas.append(_sep())
        lineas.append(_c("VENTAS POR DUENO"))
        lineas.append(_sep())

        def renglon(etiqueta, monto):
            """'etiqueta ..... $monto' a ANCHO; si no cabe, el monto baja a la derecha."""
            precio = f"${monto:.2f}"
            if len(etiqueta) + 1 + len(precio) <= ANCHO:
                return [etiqueta + precio.rjust(ANCHO - len(etiqueta))]
            return [etiqueta[:ANCHO], precio.rjust(ANCHO)]

        def renglon_concepto(c):
            """'  - Concepto x14   $860.00' en UNA línea: se recorta el concepto, no el monto."""
            sufijo = f" x{c['cantidad']}"
            cabe = ANCHO - len("  - ") - len(sufijo) - 1 - len(f"${c['total']:.2f}")
            concepto = c["concepto"]
            if len(concepto) > cabe:
                concepto = concepto[:max(cabe - 1, 0)].rstrip() + "."
            return renglon(f"  - {concepto}{sufijo}", c["total"])

        def renglones_pago(c):
            """
            Cómo lo pagó el cliente (no dónde quedó). "Pago ..." y no
            "Efectivo:"/"Tarjeta:", que son las líneas de las filas especiales.
            """
            return (renglon("      Pago efectivo:", c["pago_efectivo"])
                    + renglon("      Pago tarjeta:", c["pago_tarjeta"]))

        aviso_sin_duena = "  (sin duena: avisar)"

        for fila in filas_duenos:
            lineas.append(f"  {fila['nombre']}"[:ANCHO])
            if fila["especial"]:
                lineas.append(aviso_sin_duena)
            # Vendio = lo que le toca (ya con descuento); caja/Clip = donde
            # quedo el dinero. La que mas vendio en cada cuenta cobra TODA la
            # tarjeta en SU Clip (reparto.py). Lo que se deben entre ellas no
            # se imprime aqui: solo sale en el dashboard de cada duena.
            lineas += renglon("  Vendio:", fila["total"])
            if fila["especial"]:
                lineas += renglon("  Efectivo:", fila["efectivo"])
                lineas += renglon("  Tarjeta:", fila["tarjeta"])
            else:
                lineas += renglon("  En su caja:", fila["efectivo"])
                lineas += renglon("  En su Clip:", fila["tarjeta"])
            serv = fila["servicios"]
            if serv:
                # Servicios (incl. "Prod. sin registro"): siempre de la
                # responsable de servicios, dentro de SU bloque.
                lineas.append(_sep_punteado().rstrip())
                if not fila["especial"]:
                    lineas += renglon("  Sus productos:", fila["productos"])
                # Cobro rápido aparte de los servicios de verdad (por concepto).
                sr = serv["sin_registro"]
                if sr:
                    lineas += renglon(f"  Sin registro x{sr['cantidad']}:", sr["total"])
                    lineas += renglones_pago(sr)
                if serv["solo_servicios"]:
                    lineas += renglon("  Servicios:", serv["solo_servicios_total"])
                    for c in serv["solo_servicios"]:
                        lineas += renglon_concepto(c)
                        lineas += renglones_pago(c)
                lineas += renglon("  Total agregado:", serv["total"])
                lineas += renglones_pago(serv)
            lineas.append(_sep("-"))
        lineas.append(_sep())
        lineas.append(_c("DETALLE DEL CORTE"))
        lineas.append(_sep())
        # Etiqueta + monto no caben en ANCHO: el monto va abajo, a la derecha.
        lineas.append("TOTAL EFECTIVO EN CAJA:")
        lineas.append(f"${total_efectivo_caja:.2f}".rjust(ANCHO))
        lineas.append("TOTAL TARJETA EN CAJA:")
        lineas.append(f"${total_tarjeta_caja:.2f}".rjust(ANCHO))
        lineas.append(_sep())

        # Efectivo por cajón físico de cada dueña (ya no "EN CAJA X DEBE
        # HABER": tras repartir cada venta, el efectivo no está todo en el
        # cajón de esta computadora). Σ líneas == total_efectivo exacto
        # (reparto.py); solo se omiten las filas con efectivo 0.
        lineas.append(_c("DEBE HABER EN EFECTIVO"))
        lineas.append(_c("POR CAJON:"))
        cajones = [f for f in filas_duenos if not f["especial"] and f["efectivo"] != 0]
        sin_cajon = [f for f in filas_duenos if f["especial"] and f["efectivo"] != 0]
        for fila in cajones:
            lineas += renglon(f"Cajon {fila['nombre']}", fila["efectivo"])
            if fila["servicios"]:
                lineas.append("  (incluye servicios)")
        for fila in sin_cajon:
            lineas += renglon(fila["nombre"], fila["efectivo"])
            lineas.append(aviso_sin_duena)
        if not cajones and not sin_cajon:
            lineas.append(_c("(sin efectivo)"))
        lineas.append(_sep_punteado().rstrip())
        lineas += renglon("TOTAL", total_efectivo_caja)
        lineas.append(_c("CUENTA BIEN."))
        lineas.append(_sep())

        # Lo cobrado con tarjeta en la terminal de cada duena. Σ == tarjeta
        # de la caja exacto; solo se omiten las filas con tarjeta 0.
        lineas.append(_c("EN LOS CLIPS"))
        clips = [f for f in filas_duenos if f["tarjeta"] != 0]
        for fila in clips:
            if fila["especial"]:
                lineas += renglon(fila["nombre"], fila["tarjeta"])
                lineas.append(aviso_sin_duena)
            else:
                lineas += renglon(f"Clip {fila['nombre']}", fila["tarjeta"])
        if not clips:
            lineas.append(_c("(sin tarjeta)"))
        lineas.append(_sep_punteado().rstrip())
        lineas += renglon("TOTAL CLIPS", total_tarjeta_caja)
        lineas.append(_sep())
        lineas.append(_c("GRACIAS POR SU TRABAJO"))

        return "\n".join(lineas)
