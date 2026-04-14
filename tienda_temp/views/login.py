from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import redirect, render
from tienda_temp.forms import ContactoForm, PerfilConfigForm
from tienda_temp.models import Cliente, Usuario, Empleado


def landing(request):
    user = request.user

    if user.is_authenticated:
        empleado = getattr(user, 'empleado', None)
        cliente = getattr(user, 'cliente', None)

        if empleado:
            rol = empleado.rol

            if rol == 'dueño':
                return redirect('tienda_temp:dashboard_dueno')

            if rol in ['cajero', 'almacenista', 'ayudante']:
                return redirect('tienda_temp:dashboard_socio')

        if cliente:
            return render(request, 'tienda/landing.html', {'cliente': cliente})

    return render(request, 'tienda/landing.html')


def obtener_usuario_por_identificador(identificador):
    # 1) Username
    try:
        return Usuario.objects.get(username=identificador)
    except Usuario.DoesNotExist:
        pass

    # 2) Email
    try:
        return Usuario.objects.get(email=identificador)
    except Usuario.DoesNotExist:
        pass

    # 3) Número de contacto (Empleado)
    try:
        empleado = Empleado.objects.get(numero_contacto=identificador)
        return empleado.user
    except Empleado.DoesNotExist:
        pass

    return None

def redirigir_por_rol(user):
    # Empleado
    try:
        rol = user.empleado.rol
        if rol == "dueño":
            return "tienda_temp:dashboard_dueno"
        if rol in ["cajero", "almacenista", "ayudante"]:
            return "tienda_temp:dashboard_socio"
    except Empleado.DoesNotExist:
        pass

    # Cliente
    try:
        user.cliente
        return "landing"
    except Cliente.DoesNotExist:
        pass

    return None


def login_user(request):

    # 🔥 Si ya está autenticado, NO puede ver login
    if request.user.is_authenticated:
        destino = redirigir_por_rol(request.user)
        return redirect(destino)

    if request.method == 'POST':
        identificador = request.POST.get('username')
        password = request.POST.get('password')

        user = obtener_usuario_por_identificador(identificador)

        if not user:
            messages.error(request, "❌ Usuario, correo o número incorrecto")
            return redirect('tienda_temp:login')

        if not user.check_password(password):
            messages.error(request, "❌ Contraseña incorrecta")
            return redirect('tienda_temp:login')

        login(request, user)
        request.user.refresh_from_db()

        destino = redirigir_por_rol(request.user)
        return redirect(destino)

    return render(request, 'tienda/login.html')




def logout_user(request):
    logout(request)
    return redirect('tienda_temp:login')


def contacto(request):
    puede_enviar = False
    form = ContactoForm()

    if hasattr(request.user, 'cliente'):
        puede_enviar = True
    elif hasattr(request.user, 'empleado'):
        messages.error(request, "Los empleados no pueden enviar mensajes.")
    else:
        messages.warning(request, "Tu cuenta no tiene un rol asignado.")

    return render(request, 'tienda/contacto.html', {
        'form': form,
        'puede_enviar': puede_enviar
    })


def aboutus(request):
    return render(request, 'tienda/about-us.html')



def configuracion_perfil(request):
    # Validar que el usuario tiene perfil de empleado
    empleado = getattr(request.user, 'empleado', None)

    if not empleado:
        messages.error(request, "Solo los empleados pueden editar su perfil.")
        return redirect('tienda_temp:landing')

    if request.method == "POST":
        form = PerfilConfigForm(
            request.POST,
            usuario=request.user,
            instance=empleado
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("tienda_temp:configuracion_perfil")
        else:
            messages.error(request, "Revisa los campos, hay errores en el formulario.")
    else:
        form = PerfilConfigForm(
            usuario=request.user,
            instance=empleado
        )

    return render(request, "tienda/profile_config.html", {"form": form})

