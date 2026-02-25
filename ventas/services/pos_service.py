from django.db import transaction
from ventas.models import Venta, VentaDetalle
from inventario.services.inventario_service import InventarioService
from inventario.models import Producto


class POSService:

    @staticmethod
    @transaction.atomic
    def crear_venta(empleado, ubicacion, carrito, pagado_efectivo, pagado_tarjeta, descuento_10=False):
        """
        carrito = [
            {"producto_id": int, "cantidad": int, "precio_aplicado": float},
            ...
        ]
        """

        detalles = []
        subtotal = 0

        # 1) Calcular subtotal usando precio_aplicado del POS
        for item in carrito:
            producto_id = item["producto_id"]              # 🔥 VIENE DEL FETCH
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

        # 4) Crear Venta
        venta = Venta.objects.create(
            empleado=empleado,
            ubicacion=ubicacion,
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            metodo_pago=POSService.determinar_metodo_pago(pagado_efectivo, pagado_tarjeta),
            pagado_efectivo=pagado_efectivo,
            pagado_tarjeta=pagado_tarjeta,
            cambio=cambio,
        )

        # 5) Crear detalles + descontar inventario
        for d in detalles:

            # A) Crear detalle
            VentaDetalle.objects.create(
                venta=venta,
                producto=d["producto"],
                cantidad=d["cantidad"],
                precio_unitario=d["precio_unitario"],
                subtotal=d["subtotal"],
            )

            # B) Salida inteligente de inventario
            origen = InventarioService.salida_inteligente(
                producto=d["producto"],
                cantidad=d["cantidad"],
                empleado=empleado,
                ubicacion_sucursal=ubicacion   # 🔥 ESTA ES LA CLAVE
            )

            d["origen_inventario"] = origen

        # 6) Regresar venta + detalles
        return {
            "venta": venta,
            "detalles": detalles
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