from django.contrib import admin
from .models import (
    Categoria,
    Producto,
    Temporada,
    Ubicacion,
    Inventario,
    TransferenciaInventario,
    Atributo,
    ValorAtributo
)

# -------------------- CATEGORÍA --------------------
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre', 'descripcion')
    search_fields = ('nombre',)
    list_filter = ('padre',)


# -------------------- PRODUCTO --------------------
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'mostrar_subcategorias', 'precio_menudeo', 'dueño', 'fecha_registro')
    search_fields = ('nombre', 'codigo_barras')
    list_filter = ('categoria', 'temporada', 'dueño', 'fecha_registro')
    date_hierarchy = 'fecha_registro'

    def mostrar_subcategorias(self, obj):
        subcats = obj.categoria.filter(padre__isnull=False)
        return ", ".join([c.nombre for c in subcats])
    mostrar_subcategorias.short_description = 'Subcategorías'


# -------------------- TEMPORADA --------------------
# -------------------- TEMPORADA --------------------
@admin.register(Temporada)
class TemporadaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rango_temporada')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('inicio_mes', 'fin_mes')

    def rango_temporada(self, obj):
        if obj.inicio_mes and obj.inicio_dia and obj.fin_mes and obj.fin_dia:
            return f"{obj.inicio_dia}/{obj.inicio_mes} → {obj.fin_dia}/{obj.fin_mes}"
        return "Sin rango"
    
    rango_temporada.short_description = "Rango"


# -------------------- UBICACIÓN --------------------
@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion')
    search_fields = ('nombre',)


# -------------------- INVENTARIO --------------------
@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'ubicacion', 'cantidad_actual')
    list_filter = ('ubicacion',)
    search_fields = ('producto__nombre', 'ubicacion__nombre')


# -------------------- TRANSFERENCIA --------------------
@admin.register(TransferenciaInventario)
class TransferenciaAdmin(admin.ModelAdmin):
    list_display = ('producto', 'origen', 'destino', 'cantidad', 'fecha', 'realizado_por')
    list_filter = ('origen', 'destino', 'fecha')
    search_fields = ('producto__nombre', 'origen__nombre', 'destino__nombre')


# -------------------- ATRIBUTO --------------------
@admin.register(Atributo)
class AtributoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria')
    list_filter = ('categoria',)
    search_fields = ('nombre', 'categoria__nombre')


# -------------------- VALOR DE ATRIBUTO --------------------
@admin.register(ValorAtributo)
class ValorAtributoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'atributo', 'valor')
    list_filter = ('atributo', 'producto')
    search_fields = ('producto__nombre', 'atributo__nombre', 'valor')
