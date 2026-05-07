from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/inventario/(?P<ubicacion_id>\d+)/$", consumers.InventarioConsumer.as_asgi()),
]
