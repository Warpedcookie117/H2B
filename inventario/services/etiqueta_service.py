from django.shortcuts import redirect
from django.contrib import messages
import base64


class EtiquetaService:

    ETIQUETAS = [
        {"nombre": "Pequeña", "tamaño": "50x20 mm", "tipo": "chica", "descripcion": "Ideal para empaques pequeños"},
        {"nombre": "Mediana", "tamaño": "100x30 mm", "tipo": "mediana", "descripcion": "Para cajas medianas o productos estándar"},
        {"nombre": "Grande", "tamaño": "135x32 mm", "tipo": "grande", "descripcion": "Para empaques grandes o logísticos"},
    ]

    @staticmethod
    def preparar_producto_sin_codigo(form, request):
        """
        Guarda los datos del formulario en sesión para continuar
        el flujo de selección de etiqueta.
        """

        cleaned = form.cleaned_data
        pendiente = {}

        # Serializar datos del formulario
        for key, value in cleaned.items():

            # Caso ManyToMany (temporada)
            if hasattr(value, "all"):
                pendiente[key] = [str(v.pk) for v in value.all()]

            # Caso ForeignKey
            elif hasattr(value, "pk"):
                pendiente[key] = value.pk

            # Caso normal
            else:
                pendiente[key] = str(value) if value is not None else None
                
                     
        pendiente["categoria_padre"] = cleaned["categoria_padre"].id
        
        # Guardar atributos dinámicos
        atributos = {
            key: value.strip()
            for key, value in request.POST.items()
            if key.startswith("atributo_") and value.strip()
        }
        pendiente["atributos"] = atributos

        # Guardar imagen en sesión (como base64)
        if "foto_url" in request.FILES:
            archivo = request.FILES["foto_url"]
            request.session["pendiente_file"] = base64.b64encode(archivo.read()).decode("utf-8")
            request.session["pendiente_file_name"] = archivo.name
            request.session["pendiente_file_type"] = archivo.content_type
        else:
            request.session["pendiente_file"] = None

        # Guardar inventario
        request.session["pendiente_producto"] = pendiente
        request.session["pendiente_inventario"] = {
            "cantidad": cleaned.get("cantidad_inicial"),
            "ubicacion_id": cleaned.get("ubicacion").id if cleaned.get("ubicacion") else None,
        }

        return redirect("inventario:seleccionar_etiqueta_temp")