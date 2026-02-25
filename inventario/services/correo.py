from django.core.mail import send_mail
from django.conf import settings

def enviar_correo(asunto, mensaje, destinatario):
    print("========== ENVÍO DE CORREO ==========")
    print("Asunto:", asunto)
    print("Mensaje:", mensaje)
    print("Destinatario:", destinatario)
    print("Remitente:", settings.DEFAULT_FROM_EMAIL)
    print("======================================")

    try:
        resultado = send_mail(
            asunto,
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            [destinatario],
            fail_silently=False,
        )

        print(">>> CORREO ENVIADO CORRECTAMENTE <<<")
        print("Resultado send_mail:", resultado)
        print("======================================")
        return True

    except Exception as e:
        print(">>> ERROR AL ENVIAR CORREO <<<")
        print("Error:", e)
        print("======================================")
        return False