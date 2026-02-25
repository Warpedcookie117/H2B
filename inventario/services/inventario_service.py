from django.core.exceptions import ValidationError
from django.db import transaction

from inventario.models import Inventario, MovimientoInventario, TransferenciaInventario, Ubicacion


class InventarioService:
    """
    Servicio de dominio para manejar movimientos de inventario:
    - Entradas
    - Salidas
    - Ajustes (positivos y negativos)
    - Transferencias (origen/destino)
    """

    MOTIVO_A_TIPO = {
        "compra": "entrada",
        "devolucion": "entrada",
        "reabastecimiento": "entrada",
        "nuevo": "entrada",

        "venta": "salida",
        "daño": "salida",
        "perdida": "salida",

        "correccion": "ajuste",
        "conteo": "ajuste",
    }

    # -----------------------------
    # API PÚBLICA
    # -----------------------------

    @staticmethod
    def entrada(producto, cantidad, destino, empleado=None, motivo="compra"):
        tipo = InventarioService._deducir_tipo(motivo, esperado="entrada")

        with transaction.atomic():
            inv_dest, _ = Inventario.objects.get_or_create(
                producto=producto,
                ubicacion=destino
            )
            inv_dest = Inventario.objects.select_for_update().get(pk=inv_dest.pk)

            inv_dest.cantidad_actual += cantidad
            inv_dest.save()

            mov = MovimientoInventario(
                producto=producto,
                tipo="entrada",
                motivo=motivo,
                cantidad=cantidad,
                origen=None,
                destino=destino,
                realizado_por=empleado,
            )
            mov.full_clean()
            mov.save()

            return inv_dest
        

    @staticmethod
    def salida(producto, cantidad, origen, empleado=None, motivo="venta"):
        tipo = InventarioService._deducir_tipo(motivo, esperado="salida")

        with transaction.atomic():
            inv_orig = Inventario.objects.select_for_update().filter(
                producto=producto,
                ubicacion=origen
            ).first()

            if not inv_orig or inv_orig.cantidad_actual < cantidad:
                raise ValidationError("Inventario insuficiente para realizar la salida.")

            inv_orig.cantidad_actual -= cantidad
            inv_orig.save()

            mov = MovimientoInventario(
                producto=producto,
                tipo="salida",
                motivo=motivo,
                cantidad=cantidad,
                origen=origen,
                destino=None,
                realizado_por=empleado,
            )
            mov.full_clean()
            mov.save()

            return inv_orig      
        
    @staticmethod
    def salida_inteligente(producto, cantidad, empleado=None, ubicacion_sucursal=None):
        piso = Ubicacion.objects.get(nombre="Piso")
        bodega = Ubicacion.objects.get(nombre="Bodega Interna")

        stock_piso = InventarioService.get_stock(producto, piso)
        stock_bodega = InventarioService.get_stock(producto, bodega)

        if cantidad <= stock_piso:
            InventarioService.salida(producto, cantidad, piso, empleado, "venta")
            return "piso"

        if cantidad <= stock_bodega:
            InventarioService.salida(producto, cantidad, bodega, empleado, "venta")
            return "bodega"

        raise ValidationError(
            f"No hay suficiente inventario para {producto.nombre}. "
            f"Piso: {stock_piso}, Bodega: {stock_bodega}, Pedido: {cantidad}"
        )

    @staticmethod
    def ajuste(producto, nueva_cantidad, ubicacion, empleado=None, motivo="conteo"):
        with transaction.atomic():
            inv = Inventario.objects.select_for_update().get(
                producto=producto,
                ubicacion=ubicacion
            )
            cantidad_actual = inv.cantidad_actual

            if nueva_cantidad == cantidad_actual:
                return inv

            diferencia = nueva_cantidad - cantidad_actual

            # AUMENTA → AJUSTE (entrada)
            if diferencia > 0:
                mov = MovimientoInventario(
                    producto=producto,
                    tipo="ajuste",
                    motivo=motivo,
                    cantidad=diferencia,
                    origen=None,
                    destino=ubicacion,
                    realizado_por=empleado,
                )
                mov.full_clean()
                mov.save()

            # DISMINUYE → SALIDA (corrección)
            else:
                mov = MovimientoInventario(
                    producto=producto,
                    tipo="salida",
                    motivo="correccion",
                    cantidad=abs(diferencia),
                    origen=ubicacion,
                    destino=None,
                    realizado_por=empleado,
                )
                mov.full_clean()
                mov.save()

            inv.cantidad_actual = nueva_cantidad
            inv.save()

            return inv
        
    @staticmethod
    def aplicar_ajuste(solicitud, empleado_responsable):
        """
        Aplica un ajuste aprobado desde el sistema (correo o panel).
        La solicitud contiene:
        - producto
        - ubicacion
        - cantidad (nueva cantidad)
        - motivo
        - usuario que solicitó el ajuste
        """

        with transaction.atomic():
            inv = Inventario.objects.select_for_update().get(
                producto=solicitud.producto,
                ubicacion=solicitud.ubicacion
            )

            cantidad_actual = inv.cantidad_actual
            nueva_cantidad = solicitud.cantidad
            diferencia = nueva_cantidad - cantidad_actual

            if diferencia == 0:
                return inv

            # AJUSTE POSITIVO
            if diferencia > 0:
                mov = MovimientoInventario(
                    producto=solicitud.producto,
                    tipo="ajuste",
                    motivo=solicitud.motivo or "correccion",
                    cantidad=diferencia,
                    origen=None,
                    destino=solicitud.ubicacion,
                    realizado_por=empleado_responsable,  # ✔ FIX
                )
                mov.full_clean()
                mov.save()

            # AJUSTE NEGATIVO
            else:
                mov = MovimientoInventario(
                    producto=solicitud.producto,
                    tipo="salida",
                    motivo="correccion",
                    cantidad=abs(diferencia),
                    origen=solicitud.ubicacion,
                    destino=None,
                    realizado_por=empleado_responsable,  # ✔ FIX
                )
                mov.full_clean()
                mov.save()

            inv.cantidad_actual = nueva_cantidad
            inv.save()

            return inv

    @staticmethod
    def transferencia(producto, cantidad, origen, destino, empleado=None):
        if cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

        with transaction.atomic():

            # 1. Crear registro administrativo de transferencia
            transferencia = TransferenciaInventario(
                producto=producto,
                cantidad=cantidad,
                origen=origen,
                destino=destino,
                realizado_por=empleado
            )
            transferencia.full_clean()
            transferencia.save()

            # 2. ORIGEN
            inv_orig = Inventario.objects.select_for_update().filter(
                producto=producto,
                ubicacion=origen
            ).first()

            if not inv_orig or inv_orig.cantidad_actual < cantidad:
                raise ValidationError("Inventario insuficiente en la ubicación de origen.")

            inv_orig.cantidad_actual -= cantidad
            inv_orig.save()

            mov_salida = MovimientoInventario(
                producto=producto,
                tipo="salida",
                motivo="transferencia",
                cantidad=cantidad,
                origen=origen,
                destino=None,
                realizado_por=empleado,
                transferencia=transferencia,
            )
            mov_salida.full_clean()
            mov_salida.save()

            # 3. DESTINO
            inv_dest, _ = Inventario.objects.get_or_create(
                producto=producto,
                ubicacion=destino
            )
            inv_dest = Inventario.objects.select_for_update().get(pk=inv_dest.pk)

            inv_dest.cantidad_actual += cantidad
            inv_dest.save()

            mov_entrada = MovimientoInventario(
                producto=producto,
                tipo="entrada",
                motivo="transferencia",
                cantidad=cantidad,
                origen=None,
                destino=destino,
                realizado_por=empleado,
                transferencia=transferencia,
            )
            mov_entrada.full_clean()
            mov_entrada.save()

            return {
                "producto_id": producto.id,
                "producto_nombre": producto.nombre,
                "cantidad_origen": inv_orig.cantidad_actual,
                "cantidad_destino": inv_dest.cantidad_actual,
                "origen_id": origen.id,
                "destino_id": destino.id,
                "remove_card": inv_orig.cantidad_actual == 0,
                "add_card": True,
            }
            
            
    @staticmethod
    def transferencia_multiple(origen, destino, productos, empleado=None):
        """
        productos = [
            {"producto": Producto, "cantidad": int},
            ...
        ]
        """

        resultados = []

        with transaction.atomic():
            for item in productos:
                producto = item["producto"]
                cantidad = item["cantidad"]

                # Reutilizamos la lógica de transferencia simple
                resultado = InventarioService.transferencia(
                    producto=producto,
                    cantidad=cantidad,
                    origen=origen,
                    destino=destino,
                    empleado=empleado
                )

                resultados.append(resultado)

        return resultados
    # -----------------------------
    # INTERNOS
    # -----------------------------

    @staticmethod
    def _deducir_tipo(motivo, esperado=None):
        tipo = InventarioService.MOTIVO_A_TIPO.get(motivo)
        if not tipo:
            raise ValidationError(f"Motivo '{motivo}' no es válido.")
        if esperado and tipo != esperado:
            raise ValidationError(
                f"El motivo '{motivo}' corresponde a un tipo '{tipo}', "
                f"pero se esperaba '{esperado}'."
            )
        return tipo
    
    @staticmethod
    def get_stock(producto, ubicacion):
        """
        Regresa el stock actual de un producto en una ubicación específica.
        """

        registro = Inventario.objects.filter(
            producto=producto,
            ubicacion=ubicacion
        ).first()

        return registro.cantidad_actual if registro else 0