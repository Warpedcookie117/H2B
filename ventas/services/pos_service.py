from django.db import transaction
from ventas.models import Venta, VentaDetalle
from inventario.services.inventario_service import InventarioService
from inventario.models import Producto
from ventas.services.ticket_service import generar_texto_ticket, imprimir_silencioso
from sucursales.models import Caja


class POSService:

    @staticmethod
    @transaction.atomic
    def crear_venta(empleado, sucursal, caja_id, carrito, pagado_efectivo, pagado_tarjeta, descuento_10=False):

        detalles = []
        subtotal = 0

        # 1) Calcular subtotal usando precio_aplicado del POS
        for item in carrito:
            producto_id = item["producto_id"]
            producto = Producto.objects.get(pk=producto_id)

            cantidad = item["cantidad"]
            precio_unitario = float(item["precio_aplicado"])

            subtotal_item = precio_unitario * cantidad
            subtotal += subtotal_item

            detalles.append({
                "producto": producto,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "subtotal": subtotal_item,
                "tipo_precio": "POS",
            })

        # 2) Descuento
        descuento = subtotal * 0.10 if descuento_10 else 0
        total = subtotal - descuento

        # 3) Validar pagos
        total_pagado = pagado_efectivo + pagado_tarjeta
        if total_pagado < total:
            raise ValueError("El pago es insuficiente.")

        # Cálculo de cambio
        cambio = pagado_efectivo - max(0, total - pagado_tarjeta)
        if cambio < 0:
            cambio = 0

        # 4) Ubicación de venta
        ubicacion_venta = sucursal.ubicaciones.get(tipo="piso")

        # 5) Snapshot del nombre de la caja
        try:
            caja = Caja.objects.get(pk=caja_id)
            caja_nombre = caja.nombre
        except Caja.DoesNotExist:
            caja_nombre = None

        # 6) Crear Venta
        venta = Venta.objects.create(
            empleado=empleado,
            ubicacion=ubicacion_venta,
            caja_id=caja_id,
            caja_nombre=caja_nombre,
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            metodo_pago=POSService.determinar_metodo_pago(pagado_efectivo, pagado_tarjeta),
            pagado_efectivo=pagado_efectivo,
            pagado_tarjeta=pagado_tarjeta,
            cambio=cambio,
        )

        # 7) Crear detalles + descontar inventario
        for d in detalles:
            producto = d["producto"]

            # Construir atributos snapshot
            atributos_snap = {
                v.atributo.nombre: v.valor
                for v in producto.valores_atributo.select_related("atributo").all()
            }

            VentaDetalle.objects.create(
                venta=venta,
                producto=producto,
                nombre_snapshot=producto.nombre,
                atributos_snapshot=atributos_snap,
                cantidad=d["cantidad"],
                precio_unitario=d["precio_unitario"],
                subtotal=d["subtotal"],
            )

            InventarioService.salida_inteligente(
                producto=producto,
                cantidad=d["cantidad"],
                empleado=empleado,
                sucursal=sucursal
            )

        # 8) Generar ticket e imprimir silenciosamente
        ticket_texto = generar_texto_ticket(venta)
        imprimir_silencioso(ticket_texto)

        # 9) Regresar venta + detalles + ticket
        return {
            "venta": venta,
            "detalles": detalles,
            "ticket_texto": ticket_texto,
        }

    @staticmethod
    def determinar_metodo_pago(efectivo, tarjeta):
        if efectivo > 0 and tarjeta > 0:
            return "mixto"
        elif efectivo > 0:
            return "efectivo"
        elif tarjeta > 0:
            return "tarjeta"
        else:
            raise ValueError("No se recibió ningún pago válido.")