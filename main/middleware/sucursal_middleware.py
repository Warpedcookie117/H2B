from sucursales.models import Sucursal, Caja

class SucursalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.sucursal_actual = None
        request.caja_actual = None

        sucursal_id = request.session.get("sucursal_actual")
        caja_id = request.session.get("caja_actual")
        print(">>> caja_id en sesión:", caja_id)
        if sucursal_id:
            try:
                request.sucursal_actual = Sucursal.objects.get(id=sucursal_id)
            except Sucursal.DoesNotExist:
                request.session.pop("sucursal_actual", None)

        if caja_id:
            try:
                request.caja_actual = Caja.objects.get(id=caja_id)
            except Caja.DoesNotExist:
                request.session.pop("caja_actual", None)

        return self.get_response(request)