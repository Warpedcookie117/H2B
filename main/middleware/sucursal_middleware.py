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

        # -------------------------
        # SUCURSAL
        # -------------------------
        if sucursal_id:
            suc = Sucursal.objects.filter(id=sucursal_id).first()
            if suc:
                request.sucursal_actual = suc
            else:
                request.session.pop("sucursal_actual", None)

        # -------------------------
        # CAJA
        # -------------------------
        if caja_id:
            caja = Caja.objects.filter(id=caja_id).first()
            if caja:
                request.caja_actual = caja
            else:
                request.session.pop("caja_actual", None)

        return self.get_response(request)