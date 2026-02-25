
from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import render, redirect
from django.shortcuts import redirect
from django.db import transaction
from tienda_temp.forms import RegistroEmpleadoForm
from tienda_temp.models import Cliente, Empleado, Usuario


def registro_empleado(request):
    # Si viene ?rol=dueño → se registra un dueño
    # Si no viene nada → se registra un empleado normal
    rol = request.GET.get("rol", None)

    # Si no viene rol en GET, el formulario usará el select del template
    initial_data = {"rol": rol} if rol else {}

    form = RegistroEmpleadoForm(request.POST or None, initial=initial_data)

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data

        # El rol final viene del formulario:
        # - Si es empleado normal → viene del select
        # - Si es dueño → viene del initial={"rol": "dueño"}
        rol_final = data["rol"]

        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password1"],
                first_name=data["first_name"],
                last_name=data["last_name"],
            )

            # LÓGICA DE ROL
            if rol_final == "dueño":
                usuario.is_superuser = True
                usuario.is_staff = True
            else:
                usuario.is_superuser = False
                usuario.is_staff = True

            usuario.save()

            Empleado.objects.create(
                user=usuario,
                edad=data["edad"],
                direccion=data["direccion"],
                numero_contacto=data["numero_contacto"],
                rol=rol_final,
                contacto_emergencia=data["contacto_emergencia"],
                descripcion_contacto_emergencia=data["descripcion_contacto_emergencia"]
            )

        messages.success(request, f"{rol_final.capitalize()} registrado exitosamente.")
        return redirect("tienda_temp:login")

    return render(request, "tienda_temp/registro_empleado.html", {"form": form})








# Registro de clientes usando formulario manual
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
            return render(request, 'tienda_temp/registro_cliente.html', {'errores': errores})

        # Crear usuario sin permisos administrativos
        user = Usuario.objects.create_user(
            username=username,
            password=password1,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.is_staff = False
        user.is_superuser = False
        user.save()

        # Asignar al grupo "Cliente"
        grupo_cliente, _ = Group.objects.get_or_create(name='Cliente')
        user.groups.add(grupo_cliente)

        # Crear instancia de Cliente
        cliente = Cliente(user=user, direccion=direccion, numero_contacto=numero_contacto)
        cliente.save()
        
        messages.success(request, "Cliente registrado exitosamente ✅.")
        return redirect('tienda_temp:login')
    
    return render(request, 'tienda_temp/registro_cliente.html')