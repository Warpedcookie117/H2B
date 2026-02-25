from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import redirect, render
from tienda_temp.forms import ContactoForm, PerfilConfigForm
from tienda_temp.models import Usuario, Empleado



def landing(request):
    user = request.user

    if user.is_authenticated:
        empleado = getattr(user, 'empleado', None)
        cliente = getattr(user, 'cliente', None)

        if empleado:
            rol = empleado.rol
            if rol == 'dueño' or user.is_superuser:
                return redirect('tienda:dashboard_dueno')
            elif rol in ['cajero', 'almacenista', 'ayudante']:
                return redirect('tienda:dashboard_socio')
        elif cliente:
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
    if user.is_superuser:
        return 'tienda:dashboard_dueno'

    if hasattr(user, 'empleado'):
        rol = user.empleado.rol

        if rol == 'dueño':
            return 'tienda:dashboard_dueno'

        if rol in ['cajero', 'almacenista', 'ayudante']:
            return 'tienda:dashboard_socio'

    if hasattr(user, 'cliente'):
        return 'tienda:landing'

    return None

def login_user(request):
    if request.method == 'POST':
        identificador = request.POST.get('username')
        password = request.POST.get('password')

        # Buscar usuario por username / email / número
        user = obtener_usuario_por_identificador(identificador)

        if user:
            # Autenticar usando el username real
            user_auth = authenticate(request, username=user.username, password=password)

            if user_auth:
                login(request, user_auth)

                destino = redirigir_por_rol(user_auth)
                if destino:
                    return redirect(destino)

                messages.error(request, "⚠️ Tu cuenta no tiene un rol válido.")
                return redirect('tienda:login')

        messages.error(request, "❌ Usuario, correo o número incorrecto")
        return redirect('tienda:login')

    return render(request, 'tienda/login.html')

# Vista de logout
def logout_user(request):
    logout(request)
    return redirect('tienda:login')


# Vista de contacto
def contacto(request):
    puede_enviar = False
    form = ContactoForm()

    if hasattr(request.user, 'cliente'):
        puede_enviar = True
    elif hasattr(request.user, 'empleado') or request.user.is_superuser:
        messages.error(request, "Los empleados no pueden enviar mensajes.")
    else:
        messages.warning(request, "Tu cuenta no tiene un rol asignado.")

    return render(request, 'tienda/contacto.html', {
        'form': form,
        'puede_enviar': puede_enviar
    })
    
    
    
# Vista de "Sobre nosotros"
def aboutus(request):
    return render(request, 'tienda/about-us.html')



def configuracion_perfil(request):
    empleado = request.user.empleado

    if request.method == "POST":
        form = PerfilConfigForm(
            request.POST,
            usuario=request.user,
            instance=empleado
        )
        if form.is_valid():
            form.save()
            return redirect("tienda:configuracion_perfil")
    else:
        form = PerfilConfigForm(
            usuario=request.user,
            instance=empleado
        )

    return render(request, "tienda/profile_config.html", {"form": form})

