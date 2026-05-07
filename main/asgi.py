import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import inventario.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(inventario.routing.websocket_urlpatterns)
    ),
})
