def generar_texto_ticket(venta):
    lineas = []
    lineas.append("COMERCIALIZADORA MODELO")
    lineas.append("------------------------------")
    lineas.append(f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}")
    lineas.append(f"Empleado: {venta.empleado.nombre}")
    lineas.append("------------------------------")

    for item in venta.detalles.all():
        lineas.append(f"{item.producto.nombre} x{item.cantidad}")
        lineas.append(f"  ${item.precio_unitario}  →  ${item.subtotal}")

    lineas.append("------------------------------")
    lineas.append(f"Subtotal: ${venta.subtotal}")
    lineas.append(f"Descuento: ${venta.descuento}")
    lineas.append(f"TOTAL: ${venta.total}")
    lineas.append("------------------------------")
    lineas.append(f"Pago efectivo: ${venta.pagado_efectivo}")
    lineas.append(f"Pago tarjeta: ${venta.pagado_tarjeta}")
    lineas.append(f"Cambio: ${venta.cambio}")
    lineas.append("------------------------------")

    return "\n".join(lineas)