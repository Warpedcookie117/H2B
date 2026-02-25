from django import forms
from inventario.services.codigo_service import CodigoService
from inventario.services.codigo_service import CodigoService
from tienda_temp.models import Empleado
from .models import Atributo, Categoria, Temporada, TransferenciaInventario, Producto, Categoria, Ubicacion, Inventario

#ACCIONES DE INVENTARIO

class AjusteInventarioForm(forms.Form):
    cantidad = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            "class": "modal-input",
            "placeholder": "Nueva cantidad"
        })
    )

    motivo = forms.ChoiceField(
        choices=[
            ('correccion', 'Corrección de inventario'),
            ('conteo', 'Conteo físico'),
        ],
        widget=forms.Select(attrs={
            "class": "modal-select"
        })
    )

         
#Formulario para agregar producto a inventario dentro de una ubicación.
class AgregarInventarioForm(forms.Form):
    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad a agregar",
        widget=forms.NumberInput(attrs={
            'class': 'modal-input',
            'placeholder': 'Ej. 10'
        })
    )


#Modelos de inventario
class TransferenciaInventarioForm(forms.ModelForm):
    class Meta:
        model = TransferenciaInventario
        fields = ["cantidad", "destino"]
        widgets = {
            "cantidad": forms.NumberInput(attrs={
                "class": "modal-input",
                "min": 1,
                "placeholder": "Cantidad a transferir"
            }),
            "destino": forms.Select(attrs={
                "class": "modal-select"
            }),
        }

    def __init__(self, *args, **kwargs):
        # Recibimos producto y origen desde la vista
        self.producto = kwargs.pop("producto", None)
        self.origen = kwargs.pop("origen", None)
        super().__init__(*args, **kwargs)

        # Filtrar ubicaciones destino (todas menos la de origen)
        if self.origen:
            self.fields["destino"].queryset = Ubicacion.objects.exclude(id=self.origen.id)

    def clean(self):
        cleaned_data = super().clean()

        cantidad = cleaned_data.get("cantidad")
        destino = cleaned_data.get("destino")

        # Validación: origen y destino no pueden ser iguales
        if destino and self.origen and destino.id == self.origen.id:
            raise forms.ValidationError("La ubicación de origen y destino no pueden ser iguales.")

        # Validación: cantidad positiva
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor que cero.")

        # Validación: stock suficiente en origen
        if self.producto and self.origen:
            inventario_origen = Inventario.objects.filter(
                producto=self.producto,
                ubicacion=self.origen
            ).first()

            if not inventario_origen:
                raise forms.ValidationError("No existe inventario en la ubicación de origen.")

            if cantidad and cantidad > inventario_origen.cantidad_actual:
                raise forms.ValidationError(
                    f"No hay suficiente inventario en {self.origen.nombre}. "
                    f"Disponible: {inventario_origen.cantidad_actual}."
                )

        return cleaned_data


class CategoriaPadreForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control"}),
        }


class SubcategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.padre = kwargs.pop("padre")
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.padre = self.padre
        if commit:
            obj.save()
        return obj
    
    

class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ["nombre", "direccion"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "border rounded px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 focus:outline-none",
                "placeholder": "Ej. Almacén Central"
            }),
            "direccion": forms.TextInput(attrs={
                "class": "border rounded px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 focus:outline-none",
                "placeholder": "Ej. Av. Universidad 123, Monterrey"
            }),
        }





class ProductoForm(forms.ModelForm):

    tipo_codigo = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    categoria_padre = forms.ModelChoiceField(
        queryset=Categoria.objects.filter(padre__isnull=True),
        label="Categoría padre",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_categoria_padre'})
    )

    subcategoria = forms.ModelChoiceField(
        queryset=Categoria.objects.none(),
        label="Subcategoría",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_subcategoria'})
    )

    cantidad_inicial = forms.IntegerField(
        label="Cantidad inicial",
        min_value=1,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Número de piezas al registrar el producto"
    )

    ubicacion = forms.ModelChoiceField(
        queryset=Ubicacion.objects.all(),
        required=True,
        label="Ubicación de registro",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Producto
        fields = [
            'nombre', 'descripcion',
            'precio_mayoreo', 'precio_menudeo', 'precio_docena',
            'foto_url', 'temporada', 'dueño',
            'codigo_barras',
            'tipo_codigo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'precio_mayoreo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'precio_menudeo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'precio_docena': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'foto_url': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'capture': 'environment'
            }),
            'temporada': forms.CheckboxSelectMultiple(),
            'dueño': forms.Select(attrs={'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_codigo': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.from_etiqueta = kwargs.pop("from_etiqueta", False)
        super().__init__(*args, **kwargs)

        self.fields['dueño'].queryset = Empleado.objects.filter(rol='dueño')

        if 'categoria_padre' in self.data:
            try:
                padre_id = int(self.data.get('categoria_padre'))
                self.fields['subcategoria'].queryset = Categoria.objects.filter(padre_id=padre_id)
            except (ValueError, TypeError):
                self.fields['subcategoria'].queryset = Categoria.objects.none()

        elif self.instance.pk and self.instance.categoria:
            padre = self.instance.categoria.padre
            self.fields['subcategoria'].queryset = Categoria.objects.filter(padre=padre)

        else:
            self.fields['subcategoria'].queryset = Categoria.objects.none()

    def clean_foto_url(self):
        foto = self.cleaned_data.get("foto_url")
        if not foto:
            raise forms.ValidationError("Debes subir una imagen del producto.")
        return foto

    def clean_subcategoria(self):
        sub = self.cleaned_data.get("subcategoria")
        if not sub or sub.padre is None:
            raise forms.ValidationError("Debes seleccionar una subcategoría válida.")
        return sub

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get("codigo_barras")

        if self.from_etiqueta:
            return codigo

        if codigo:
            codigo = str(codigo).strip()

            try:
                CodigoService.validar_codigo_real(codigo)
            except ValueError as e:
                raise forms.ValidationError(str(e))

            if Producto.objects.filter(codigo_barras=codigo).exists():
                raise forms.ValidationError("Ya existe un producto con este código de barras.")

            return codigo

        return None

    # 🔥 VALIDACIÓN DE ATRIBUTOS DINÁMICOS
    def clean(self):
        cleaned = super().clean()

        sub = cleaned.get("subcategoria")
        if not sub:
            return cleaned

        from inventario.models import Atributo
        atributos = Atributo.objects.filter(categoria=sub)

        errores = []

        for atributo in atributos:
            key = f"atributo_{atributo.id}"
            valor = (self.data.get(key) or "").strip()

            if valor == "":
                errores.append(f"El atributo '{atributo.nombre}' es obligatorio.")
            elif valor.lower() == "n/a":
                cleaned[key] = "N/A"
            else:
                cleaned[key] = valor

        if errores:
            raise forms.ValidationError(errores)

        return cleaned

    def save(self, commit=True):
        producto = super().save(commit=False)

        if commit:
            producto.save()
            self.save_m2m()

        return producto



class TemporadaForm(forms.ModelForm):
    class Meta:
        model = Temporada
        fields = [
            "nombre",
            "descripcion",
            "inicio_mes",
            "inicio_dia",
            "fin_mes",
            "fin_dia",
        ]

    def clean(self):
        cleaned = super().clean()

        im = cleaned.get("inicio_mes")
        idia = cleaned.get("inicio_dia")
        fm = cleaned.get("fin_mes")
        fdia = cleaned.get("fin_dia")

        # Si no llenan fechas, no pasa nada (son opcionales)
        if not all([im, idia, fm, fdia]):
            return cleaned

        # Validación simple: inicio debe ser antes que fin
        inicio = (im, idia)
        fin = (fm, fdia)

        if fin < inicio:
            raise forms.ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )

        return cleaned
    
class AtributoForm(forms.ModelForm):
    class Meta:
        model = Atributo
        fields = ["nombre", "tipo"]
        widgets = {
            "nombre": forms.TextInput(),
            "tipo": forms.Select(),
        }
