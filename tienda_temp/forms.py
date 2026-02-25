from django import forms
from django.contrib.auth.models import Group
from django import forms
from django.contrib.auth import get_user_model
from django import forms
from tienda_temp.models import Empleado, Usuario



class RegistroEmpleadoForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))

    edad = forms.IntegerField(
        min_value=16,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    direccion = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    numero_contacto = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    contacto_emergencia = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    descripcion_contacto_emergencia = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    # Campo oculto para dueño
    rol = forms.CharField(
        widget=forms.HiddenInput(),
        initial="empleado"
    )

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError("Las contraseñas no coinciden.")

        if Usuario.objects.filter(username=cleaned.get("username")).exists():
            raise forms.ValidationError("El nombre de usuario ya existe.")

        if Usuario.objects.filter(email=cleaned.get("email")).exists():
            raise forms.ValidationError("El correo ya está registrado.")

        if Empleado.objects.filter(numero_contacto=cleaned.get("numero_contacto")).exists():
            raise forms.ValidationError("El número de contacto ya está registrado.")

        return cleaned




class RegistroClienteForm(forms.Form):
    username = forms.CharField()
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    first_name = forms.CharField()
    last_name = forms.CharField()

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError("Las contraseñas no coinciden.")

        if Usuario.objects.filter(username=cleaned.get("username")).exists():
            raise forms.ValidationError("El nombre de usuario ya existe.")

        if Usuario.objects.filter(email=cleaned.get("email")).exists():
            raise forms.ValidationError("El correo ya está registrado.")

        return cleaned







class LoginForm(forms.Form):
    identificador = forms.CharField(label="Usuario / Correo / Número", required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)




class ContactoForm(forms.Form):
    nombre = forms.CharField(label='Nombre', max_length=100)
    email = forms.EmailField(label='Correo electrónico')
    mensaje = forms.CharField(label='Mensaje', widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            attrs = {'class': 'form-control'}
            if field_name == 'mensaje':
                attrs['placeholder'] = 'Escribe tu mensaje aquí'
            elif field_name == 'email':
                attrs['placeholder'] = 'Tu correo'
            elif field_name == 'nombre':
                attrs['placeholder'] = 'Tu nombre'

            field.widget.attrs.update(attrs)
            
            


class PerfilConfigForm(forms.ModelForm):
    username = forms.CharField(label="Nombre de usuario", required=True)
    first_name = forms.CharField(label="Nombre", required=True)
    last_name = forms.CharField(label="Apellidos", required=True)
    email = forms.EmailField(label="Correo electrónico", required=True)

    class Meta:
        model = Empleado
        fields = [
            "direccion",
            "numero_contacto",
            "edad",
            "contacto_emergencia",
            "descripcion_contacto_emergencia",
        ]

    def __init__(self, *args, **kwargs):
        usuario = kwargs.pop("usuario")
        super().__init__(*args, **kwargs)

        # Prellenar datos del usuario
        self.fields["username"].initial = usuario.username
        self.fields["first_name"].initial = usuario.first_name
        self.fields["last_name"].initial = usuario.last_name
        self.fields["email"].initial = usuario.email

    def save(self, commit=True):
        empleado = super().save(commit=False)
        usuario = empleado.user

        usuario.username = self.cleaned_data["username"]
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data["last_name"]
        usuario.email = self.cleaned_data["email"]

        if commit:
            usuario.save()
            empleado.save()

        return empleado



