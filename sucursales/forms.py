from django import forms
from sucursales.models import Caja, Sucursal

class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ["nombre", "direccion"]
        



class CajaForm(forms.ModelForm):
    class Meta:
        model = Caja
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Nombre de la caja (ej. Caja 1)"
            })
        }