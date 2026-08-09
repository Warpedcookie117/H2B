"""
Borra de Cloudinary las fotos que ya ningún producto referencia.

De dónde salen: hasta que se agregó el borrado automático en signals.py, cada
vez que alguien cambiaba la foto de un producto Django subía la nueva y dejaba
la anterior en Cloudinary para siempre. También quedan las de productos que se
eliminaron por completo.

ESTO BORRA ORIGINALES Y ES PERMANENTE.
Una miniatura borrada se regenera sola; un original borrado no vuelve. Por eso
no borra nada salvo que se le pase --confirmar.

CÓMO DISTINGUE UNA FOTO EN USO DE UNA HUÉRFANA
----------------------------------------------
Comparación de texto exacto contra la columna foto_url de inventario_producto,
que es el ÚNICO campo del proyecto que guarda imágenes (verificado: no hay otro
ImageField ni FileField en ninguna app).

Un producto inactivo o desactivado conserva su foto_url en la base, así que
cuenta como en uso y no se toca.

Tres protecciones contra falsos positivos:

1. Si la consulta a la base devuelve vacío, aborta. Sin esa guarda, un fallo de
   conexión haría que TODO pareciera huérfano.

2. No recorta la extensión en el último punto, sino solo si lo que sigue es una
   extensión de imagen conocida. Hay nombres como
   "Captura_de_pantalla_..._4.53.11p.m._gemqmj" que un rsplit(".") destrozaría,
   haciendo que una foto EN USO pareciera huérfana.

3. Ignora lo subido en los últimos --dias-de-gracia días. Si alguien sube una
   foto mientras el comando corre, aparecería en Cloudinary pero no en el
   snapshot de la base. Una foto de hace minutos no puede ser huérfana legítima.

Uso:
    python manage.py limpiar_fotos_huerfanas                 # solo reporta
    python manage.py limpiar_fotos_huerfanas --confirmar
    python manage.py limpiar_fotos_huerfanas --incluir-samples --incluir-thumbs
"""

from datetime import datetime, timedelta, timezone

import cloudinary
import cloudinary.api
from django.core.management.base import BaseCommand, CommandError

from inventario.models import Producto

# Carpetas con basura conocida, que no son huérfanas "normales":
#   samples/  → imágenes y videos de demo que Cloudinary mete en toda cuenta nueva.
#   thumbs/   → restos del campo foto_thumbnail (migración 0016, revertida en 0018).
PREFIJO_SAMPLES = "samples/"
PREFIJO_THUMBS = "media/productos/thumbs/"

EXTENSIONES = {
    "jpg", "jpeg", "png", "webp", "gif", "heic", "heif",
    "avif", "bmp", "tif", "tiff",
}

# delete_resources acepta 100 public_ids por llamada.
TAMAÑO_LOTE = 100

# Si más de este porcentaje sale borrable, algo está mal en el cruce y es mejor
# detenerse que borrar medio catálogo.
UMBRAL_SOSPECHA = 40.0


class Command(BaseCommand):
    help = "Borra fotos de Cloudinary que ningún producto referencia."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar", action="store_true",
            help="Ejecuta el borrado. Sin esta bandera solo reporta.",
        )
        parser.add_argument(
            "--dias-de-gracia", type=int, default=7,
            help="No tocar nada subido en los últimos N días (default: 7).",
        )
        parser.add_argument(
            "--incluir-samples", action="store_true",
            help="Incluye las imágenes de demo de Cloudinary (samples/).",
        )
        parser.add_argument(
            "--incluir-thumbs", action="store_true",
            help="Incluye los restos de foto_thumbnail (media/productos/thumbs/).",
        )
        parser.add_argument(
            "--forzar", action="store_true",
            help="Ignora la guarda del porcentaje. Solo si revisaste la lista.",
        )

    # ------------------------------------------------------------------

    def handle(self, *args, **opts):
        cfg = cloudinary.config()
        if not (cfg.cloud_name and cfg.api_key and cfg.api_secret):
            raise CommandError(
                "Faltan credenciales de Cloudinary. Corre esto en el servidor, "
                "con las variables CLOUDINARY_* cargadas."
            )
        self.stdout.write(f"Cuenta: {cfg.cloud_name}")

        referenciadas, cuantos_productos = self._referenciadas()

        # GUARDA CRÍTICA: sin esto, un fallo de la base haría que absolutamente
        # todo pareciera huérfano y borraríamos el catálogo entero.
        if not referenciadas:
            raise CommandError(
                "La base de datos no devolvió ninguna foto referenciada. Eso no "
                "puede ser correcto — abortando sin tocar nada."
            )

        en_nube, creado = self._en_nube()
        if not en_nube:
            raise CommandError("Cloudinary no devolvió recursos — abortando.")

        grupos = self._clasificar(en_nube, creado, referenciadas, opts["dias_de_gracia"])
        self._reportar(en_nube, cuantos_productos, grupos, opts["dias_de_gracia"])

        objetivo = dict(grupos["huerfanas"])
        if opts["incluir_samples"]:
            objetivo.update(grupos["samples"])
        if opts["incluir_thumbs"]:
            objetivo.update(grupos["thumbs"])

        if not objetivo:
            self.stdout.write(self.style.SUCCESS("\nNada que borrar."))
            return

        porcentaje = 100.0 * len(objetivo) / len(en_nube)
        if porcentaje > UMBRAL_SOSPECHA and not opts["forzar"]:
            raise CommandError(
                f"\nEl {porcentaje:.1f}% de los recursos salió borrable (umbral "
                f"{UMBRAL_SOSPECHA}%). Eso apunta a un problema en el cruce, no a "
                f"tanta basura real. Revisa la lista; si de verdad es correcto, "
                f"repite con --forzar."
            )

        self.stdout.write("\nLas 10 más pesadas de las que se borrarían:")
        for pid, tam in sorted(objetivo.items(), key=lambda x: -x[1])[:10]:
            self.stdout.write(f"  {tam / 1024 ** 2:7.2f} MB  {pid}")

        if not opts["confirmar"]:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN — no se borró nada. Repite con --confirmar para "
                f"borrar {len(objetivo)} fotos ({sum(objetivo.values())/1024**3:.2f} GB)."
            ))
            return

        self._borrar(sorted(objetivo))

    # ------------------------------------------------------------------

    def _referenciadas(self):
        """
        Los nombres que la base apunta, en las dos formas en que pueden
        aparecer: tal cual, y sin extensión (Cloudinary guarda el public_id
        sin ella).
        """
        crudos = [
            str(v) for v in Producto.objects
            .exclude(foto_url="")
            .exclude(foto_url__isnull=True)
            .values_list("foto_url", flat=True)
        ]
        nombres = set()
        for n in crudos:
            nombres.add(n)
            base, punto, ext = n.rpartition(".")
            if punto and ext.lower() in EXTENSIONES:
                nombres.add(base)
        return nombres, len(crudos)

    def _en_nube(self):
        """({public_id: bytes}, {public_id: created_at}) de la cuenta."""
        tam, creado = {}, {}
        cursor = None
        while True:
            r = cloudinary.api.resources(
                type="upload", resource_type="image",
                max_results=500, next_cursor=cursor,
            )
            for x in r.get("resources", []):
                tam[x["public_id"]] = x.get("bytes", 0)
                creado[x["public_id"]] = x.get("created_at", "")
            cursor = r.get("next_cursor")
            if not cursor:
                break
        return tam, creado

    def _clasificar(self, en_nube, creado, referenciadas, dias_gracia):
        corte = (datetime.now(timezone.utc) - timedelta(days=dias_gracia)) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")

        g = {k: {} for k in ("en_uso", "huerfanas", "recientes", "samples", "thumbs")}
        for pid, tam in en_nube.items():
            if pid in referenciadas:
                g["en_uso"][pid] = tam
            elif pid.startswith(PREFIJO_SAMPLES):
                g["samples"][pid] = tam
            elif pid.startswith(PREFIJO_THUMBS):
                g["thumbs"][pid] = tam
            elif creado.get(pid, "") >= corte:
                g["recientes"][pid] = tam
            else:
                g["huerfanas"][pid] = tam
        return g

    def _reportar(self, en_nube, cuantos_productos, g, dias_gracia):
        def linea(etiqueta, d):
            gb = sum(d.values()) / 1024 ** 3
            self.stdout.write(f"  {etiqueta:<38} {len(d):5d}  {gb:6.2f} GB")

        self.stdout.write(f"\n{len(en_nube)} imágenes en Cloudinary:\n")
        linea("en uso (no se tocan)", g["en_uso"])
        linea("HUÉRFANAS (se borrarían)", g["huerfanas"])
        linea(f"subidas hace <{dias_gracia} días (protegidas)", g["recientes"])
        linea("samples/ (--incluir-samples)", g["samples"])
        linea("thumbs/ (--incluir-thumbs)", g["thumbs"])

        # Señal de salud del cruce: si algún producto de la base no apareció en
        # Cloudinary, la comparación de nombres tiene un hueco y hay que
        # revisarla ANTES de borrar nada.
        faltantes = cuantos_productos - len(g["en_uso"])
        self.stdout.write("")
        if faltantes == 0:
            self.stdout.write(self.style.SUCCESS(
                f"  Cruce sano: los {cuantos_productos} productos con foto de la "
                f"base se encontraron en Cloudinary."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"  ATENCIÓN: {faltantes} productos de la base NO se encontraron "
                f"en Cloudinary. Puede ser normal (fotos borradas a mano) o puede "
                f"significar que la comparación de nombres falla. Revísalo antes "
                f"de usar --confirmar."
            ))

    def _borrar(self, public_ids):
        lotes = (len(public_ids) + TAMAÑO_LOTE - 1) // TAMAÑO_LOTE
        self.stdout.write(f"\nBorrando {len(public_ids)} fotos en {lotes} lotes...")

        borradas = fallidas = 0
        for i in range(0, len(public_ids), TAMAÑO_LOTE):
            lote = public_ids[i:i + TAMAÑO_LOTE]
            n = i // TAMAÑO_LOTE + 1
            try:
                r = cloudinary.api.delete_resources(lote, invalidate=True)
                borradas += sum(1 for v in r.get("deleted", {}).values()
                                if v == "deleted")
            except Exception as e:
                fallidas += len(lote)
                self.stderr.write(self.style.ERROR(f"  lote {n}/{lotes} falló: {e}"))
                continue
            self.stdout.write(f"  lote {n}/{lotes} listo")

        self.stdout.write(self.style.SUCCESS(f"\n{borradas} fotos borradas."))
        if fallidas:
            self.stdout.write(self.style.WARNING(
                f"{fallidas} no se pudieron borrar — vuelve a correr el comando."
            ))
