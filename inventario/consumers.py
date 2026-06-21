import json
from channels.generic.websocket import AsyncWebsocketConsumer


class InventarioConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ubicacion_id = self.scope["url_route"]["kwargs"]["ubicacion_id"]
        self.group_name = f"inventario_{self.ubicacion_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # El browser solo escucha, no manda mensajes

    async def stock_update(self, event):
        await self.send(text_data=json.dumps({
            "tipo": "stock_update",
            "producto_id": event["producto_id"],
            "ubicacion_id": event["ubicacion_id"],
            "cantidad_actual": event["cantidad_actual"],
        }))

    async def producto_update(self, event):
        # Cambio en el detalle del producto (nombre, precios, código, foto, atributos)
        await self.send(text_data=json.dumps({
            "tipo": "producto_update",
            "producto_id": event["producto_id"],
            "nombre": event["nombre"],
            "precio_menudeo": event["precio_menudeo"],
            "precio_mayoreo": event["precio_mayoreo"],
            "precio_docena": event["precio_docena"],
            "codigo_barras": event["codigo_barras"],
            "foto_url": event["foto_url"],
            "atributos_json": event["atributos_json"],
            "categoria_id": event["categoria_id"],
            "categoria_padre_id": event["categoria_padre_id"],
            "activo": event["activo"],
        }))
