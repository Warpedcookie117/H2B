from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import transaction
from tienda_temp.forms import RegistroEmpleadoForm
from tienda_temp.models import Cliente, Empleado, Usuario


def registro_empleado(request):

    # 1. Leer el rol desde la URL (GET)
    rol_url = request.GET.get("rol", None)

    if request.method == "POST":
        # 2. POST normal
        form = RegistroEmpleadoForm(request.POST)
    else:
        # 3. GET → prellenar el rol si viene en la URL
        if rol_url:
            form = RegistroEmpleadoForm(initial={"rol": rol_url})
        else:
            form = RegistroEmpleadoForm()

    # 4. Procesar POST
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data

        with transaction.atomic():
            usuario = Usuario(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_superuser=False,
                is_staff=True,
            )
            usuario.set_password(data["password1"])
            usuario.save()

            Empleado.objects.create(
                user=usuario,
                edad=data["edad"],
                direccion=data["direccion"],
                numero_contacto=data["numero_contacto"],
                rol=data["rol"],  # 🔥 AQUÍ YA LLEGA "dueño" SI VIENE DE LA URL
                contacto_emergencia=data["contacto_emergencia"],
                descripcion_contacto_emergencia=data["descripcion_contacto_emergencia"]
            )

        messages.success(request, "Empleado registrado exitosamente.")
        return redirect("tienda_temp:login")

    return render(request, "tienda/registro_empleado.html", {"form": form})





# -----------------------------
# REGISTRO DE CLIENTES
# -----------------------------
def registro_cliente(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        direccion = request.POST.get('direccion')
        numero_contacto = request.POST.get('numero_contacto')

        errores = []

        if password1 != password2:
            errores.append("Las contraseñas no coinciden.")
        if Usuario.objects.filter(username=username).exists():
            errores.append("El nombre de usuario ya está registrado.")
        if Usuario.objects.filter(email=email).exists():
            errores.append("Este correo ya está registrado.")

        if errores:
            return render(request, 'tienda/registro_cliente.html', {'errores': errores})

        # Crear usuario normal (sin permisos administrativos)
        user = Usuario.objects.create_user(
            username=username,
            password=password1,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        # 🔥 Corrección: ningún cliente es staff o superuser
        user.is_staff = False
        user.is_superuser = False
        user.save()

        # Crear perfil de Cliente
        Cliente.objects.create(
            user=user,
            direccion=direccion,
            numero_contacto=numero_contacto
        )

        messages.success(request, "Cliente registrado exitosamente ✅.")
        return redirect('tienda_temp:login')

    return render(request, 'tienda/registro_cliente.html')