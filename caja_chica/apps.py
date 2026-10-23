from django.apps import AppConfig


class CajaChicaConfig(AppConfig):
    """
    Caja chica: el dinero que sale de la caja sin ser una venta. Vales
    (préstamos a empleados) y gastos ("¿Compraste algo?"). Siempre salen de
    la cajita de la responsable de servicios de la sucursal.

    Capas (de adentro hacia afuera; cada una solo conoce a las de adentro):
      domain/          reglas puras, sin Django
      application/     casos de uso; hablan con puertos (interfaces)
      infrastructure/  modelos y repositorios de Django que cumplen los puertos
      views/, urls.py  HTTP delgado: traduce peticiones a casos de uso
      api.py           lo único que usan las otras apps (corte, dashboard)
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "caja_chica"
    verbose_name = "Caja chica"
