# tickets/ticket_service.py

def generar_texto_ticket(obj):
    """
    Genera texto para tickets de Venta o CorteCaja.
    Detecta el tipo automáticamente.
    """

    lineas = []
    lineas.append("COMERCIALIZADORA MODELO")
    lineas.append("------------------------------")

    # Importar aquí para evitar import circular
    from ventas.models import Venta, CorteCaja

    # ============================================================
    # TICKET DE VENTA
    # ============================================================
    if isinstance(obj, Venta):
        venta = obj

        # Obtener nombre del empleado correctamente
        empleado_user = venta.empleado.user
        nombre_empleado = empleado_user.get_full_name() or empleado_user.username

        lineas.append("====== TICKET DE VENTA ======")
        lineas.append(f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}")
        lineas.append(f"Empleado: {nombre_empleado}")
        lineas.append("------------------------------")

        # Detalles de la venta
        for item in venta.detalles.all():
            lineas.append(f"{item.producto.nombre} x{item.cantidad}")
            lineas.append(f"  ${item.precio_unitario}  →  ${item.subtotal}")

        lineas.append("------------------------------")
        lineas.append(f"Subtotal: ${venta.subtotal:.2f}")
        lineas.append(f"Descuento: ${venta.descuento:.2f}")
        lineas.append(f"TOTAL: ${venta.total:.2f}")
        lineas.append("------------------------------")
        lineas.append(f"Efectivo: ${venta.pagado_efectivo:.2f}")
        lineas.append(f"Tarjeta: ${venta.pagado_tarjeta:.2f}")
        lineas.append(f"Cambio: ${venta.cambio:.2f}")
        lineas.append("------------------------------")
        lineas.append("Gracias por su compra.")
        lineas.append("------------------------------")

        return "\n".join(lineas)

    # ============================================================
    # TICKET DE CORTE DE CAJA
    # ============================================================
    if isinstance(obj, CorteCaja):
        corte = obj

        lineas.append("====== CORTE DE CAJA ======")
        lineas.append(f"Fecha: {corte.fecha.strftime('%d/%m/%Y %H:%M')}")
        lineas.append(f"Caja: {corte.caja.nombre}")
        lineas.append("------------------------------")

        lineas.append(f"TOTAL GENERAL: ${corte.total_general:.2f}")
        lineas.append("------------------------------")
        lineas.append("Totales por dueño:")

        for dueno, total in corte.total_por_dueno.items():
            lineas.append(f"{dueno}: ${total:.2f}")

        lineas.append("------------------------------")
        lineas.append("Gracias por su trabajo.")
        lineas.append("------------------------------")

        return "\n".join(lineas)

    # ============================================================
    # OBJETO NO SOPORTADO
    # ============================================================
    raise ValueError("Objeto no soportado para generar ticket.")
