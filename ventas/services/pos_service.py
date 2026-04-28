from django.db import transaction
from ventas.models import Venta, VentaDetalle, Promocion
from inventario.services.inventario_service import InventarioService
from inventario.models import Producto
from ventas.services.ticket_service import generar_texto_ticket, imprimir_silencioso
from sucursales.models import Caja


class POSService:

    @staticmethod
    def _cap_regalos(carrito):
        """Limita la cantidad de cada regalo a los productos disparadores presentes en el carrito."""
        items_normales = [i for i in carrito if not i.get("es_regalo") and not i.get("es_servicio")]

        # Precarga categorías de los productos normales
        ids_normales = [int(i["producto_id"]) for i in items_normales if i.get("producto_id")]
        prods_cache = {
            p.id: p
            for p in Producto.objects.filter(pk__in=ids_normales).select_related("categoria__padre")
        } if ids_normales else {}

        promos_cache = {}

        for item in carrito:
            if not item.get("es_regalo"):
                continue

            cantidad = int(item.get("cantidad", 1))
            promo_id = item.get("promo_id")
            max_permitido = 1  # mínimo conservador

            if promo_id:
                if promo_id not in promos_cache:
                    promos_cache[promo_id] = (
                        Promocion.objects
                        .select_related("categoria_disparadora")
                        .filter(pk=promo_id, activo=True)
                        .first()
                    )
                promo = promos_cache[promo_id]

                if promo and promo.tipo_condicion == "categoria" and promo.categoria_disparadora:
                    cat_id = promo.categoria_disparadora_id
                    max_permitido = 0
                    for ni in items_normales:
                        p = prods_cache.get(int(ni["producto_id"]))
                        if p and (
                            p.categoria_id == cat_id or
                            (p.categoria and p.categoria.padre_id == cat_id)
                        ):
                            max_permitido += int(ni.get("cantidad", 1))
                    # Si no se encontraron disparadores (ej. promo editada entre tanto), permitir 1
                    if max_permitido == 0:
                        max_permitido = 1
                # promo de monto → max 1

            item["cantidad"] = min(cantidad, max_permitido)

    @staticmethod
    @transaction.atomic
    def crear_venta(empleado, sucursal, caja_id, carrito, pagado_efectivo, pagado_tarjeta, descuento_10=False):

        POSService._cap_regalos(carrito)

        detalles = []
        subtotal = 0

        # 1) Calcular subtotal usando precio_aplicado del POS
        for item in carrito:
            cantidad       = int(item["cantidad"])
            precio_unitario = float(item["precio_aplicado"])
            subtotal_item  = precio_unitario * cantidad
            subtotal      += subtotal_item

            if item.get("es_servicio"):
                detalles.append({
                    "tipo": "servicio",
                    "producto":        None,
                    "nombre_snapshot": f"Servicio: {item.get('nombre_servicio', 'Servicio')}",
                    "cantidad":        cantidad,
                    "precio_unitario": precio_unitario,
                    "subtotal":        subtotal_item,
                    "atributos_snap":  {"tipo": "servicio"},
                })
            elif item.get("es_regalo"):
                producto = Producto.objects.get(pk=item["producto_id"])
                detalles.append({
                    "tipo":            "regalo",
                    "producto":        producto,
                    "nombre_snapshot": producto.nombre,
                    "cantidad":        cantidad,
                    "precio_unitario": 0,
                    "subtotal":        0,
                    "atributos_snap":  {"tipo": "regalo", "promo": item.get("promo_nombre", "")},
                })
            else:
                producto = Producto.objects.get(pk=item["producto_id"])
                detalles.append({
                    "tipo":            "normal",
                    "producto":        producto,
                    "nombre_snapshot": producto.nombre,
                    "cantidad":        cantidad,
                    "precio_unitario": precio_unitario,
                    "subtotal":        subtotal_item,
                    "atributos_snap":  None,
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
            if d["tipo"] == "servicio":
                VentaDetalle.objects.create(
                    venta=venta,
                    producto=None,
                    nombre_snapshot=d["nombre_snapshot"],
                    atributos_snapshot=d["atributos_snap"],
                    cantidad=d["cantidad"],
                    precio_unitario=d["precio_unitario"],
                    subtotal=d["subtotal"],
                )
            else:
                producto = d["producto"]
                atributos_snap = d["atributos_snap"] or {
                    v.atributo.nombre: v.valor
                    for v in producto.valores_atributo.select_related("atributo").all()
                }
                VentaDetalle.objects.create(
                    venta=venta,
                    producto=producto,
                    nombre_snapshot=d["nombre_snapshot"],
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