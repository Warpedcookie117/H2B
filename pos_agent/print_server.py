import base64
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 12345
CONFIG_FILE = Path(os.path.expanduser("~")) / ".pos_agent.json"


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {"printer": "", "printer_etiquetas": ""}


def save_config(data):
    CONFIG_FILE.write_text(json.dumps(data))


def print_raw(texto, printer_name):
    import win32print
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(hprinter, 1, ("Ticket POS", None, "RAW"))
        win32print.StartPagePrinter(hprinter)
        win32print.WritePrinter(hprinter, texto.encode("cp437", errors="replace") + b"\n\n\n\n")
        win32print.EndPagePrinter(hprinter)
        win32print.EndDocPrinter(hprinter)
    finally:
        win32print.ClosePrinter(hprinter)


def print_image(imagen_base64, printer_name):
    import win32ui
    import win32con
    from PIL import Image, ImageWin

    img_bytes = base64.b64decode(imagen_base64)
    img = Image.open(io.BytesIO(img_bytes))

    img_dpi = img.info.get("dpi", (203, 203))
    if isinstance(img_dpi, (int, float)):
        img_dpi = (img_dpi, img_dpi)
    dpi_x, dpi_y = max(float(img_dpi[0]), 1.0), max(float(img_dpi[1]), 1.0)

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    pdc = win32ui.CreateDC()
    pdc.CreatePrinterDC(printer_name)

    printer_dpi_x = pdc.GetDeviceCaps(win32con.LOGPIXELSX)
    printer_dpi_y = pdc.GetDeviceCaps(win32con.LOGPIXELSY)
    printer_w = pdc.GetDeviceCaps(win32con.HORZRES)
    printer_h = pdc.GetDeviceCaps(win32con.VERTRES)

    img_w, img_h = img.size
    out_w = int(img_w * printer_dpi_x / dpi_x)
    out_h = int(img_h * printer_dpi_y / dpi_y)

    if out_w > printer_w or out_h > printer_h:
        scale = min(printer_w / out_w, printer_h / out_h)
        out_w = int(out_w * scale)
        out_h = int(out_h * scale)

    pdc.StartDoc("Etiqueta")
    pdc.StartPage()
    dib = ImageWin.Dib(img)
    dib.draw(pdc.GetHandleOutput(), (0, 0, out_w, out_h))
    pdc.EndPage()
    pdc.EndDoc()
    pdc.DeleteDC()


def list_printers():
    import win32print
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def enum_jobs(printer_name):
    """Lista jobs en cola de la impresora con su status."""
    import win32print
    try:
        hprinter = win32print.OpenPrinter(printer_name)
    except Exception:
        return []
    try:
        jobs = win32print.EnumJobs(hprinter, 0, 999, 1)
    except Exception:
        jobs = []
    finally:
        win32print.ClosePrinter(hprinter)

    out = []
    for j in jobs:
        st = j.get("Status", 0)
        flags = []
        if st & 0x01: flags.append("Pausado")
        if st & 0x02: flags.append("Error")
        if st & 0x08: flags.append("En spooler")
        if st & 0x10: flags.append("Imprimiendo")
        if st & 0x20: flags.append("Offline")
        if st & 0x40: flags.append("Sin papel")
        if st & 0x80: flags.append("Impreso")
        out.append({
            "id": j.get("JobId"),
            "document": j.get("Document", ""),
            "status_flags": flags or ["Pendiente"],
        })
    return out


def diagnostico(printer_name, espera_s=1.5):
    """Espera y devuelve estado fisico + jobs pendientes despues de imprimir."""
    import time
    time.sleep(espera_s)
    return {
        "printer": printer_info(printer_name),
        "jobs": enum_jobs(printer_name),
    }


def printer_info(name):
    """Devuelve estado de la impresora consultando Windows.
    exists=False si no esta instalada; online=False si esta apagada o desconectada."""
    import win32print
    try:
        hprinter = win32print.OpenPrinter(name)
    except Exception:
        return {"exists": False, "online": False, "status_text": "No instalada"}
    try:
        info  = win32print.GetPrinter(hprinter, 2)
        st    = info.get("Status", 0)
        attrs = info.get("Attributes", 0)
        # PRINTER_STATUS_OFFLINE = 0x80, PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x400
        if (st & 0x80) or (attrs & 0x400):
            return {"exists": True, "online": False, "status_text": "Apagada o desconectada"}
        if st & 0x10: return {"exists": True, "online": True, "status_text": "Sin papel"}
        if st & 0x08: return {"exists": True, "online": True, "status_text": "Atasco de papel"}
        if st & 0x02: return {"exists": True, "online": True, "status_text": "Error"}
        if st & 0x400000: return {"exists": True, "online": False, "status_text": "Sin energia"}  # POWER_SAVE
        return {"exists": True, "online": True, "status_text": "Lista"}
    finally:
        win32print.ClosePrinter(hprinter)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            cfg = load_config()
            self._send(200, {
                "ok": True,
                "printer": cfg.get("printer", ""),
                "printer_etiquetas": cfg.get("printer_etiquetas", ""),
            })
        elif self.path == "/printers":
            try:
                self._send(200, {"printers": list_printers()})
            except Exception as e:
                self._send(500, {"error": str(e)})
        elif self.path.startswith("/printer-info"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = (qs.get("name") or [""])[0]
            if not name:
                self._send(400, {"error": "Falta name"})
                return
            try:
                self._send(200, printer_info(name))
            except Exception as e:
                self._send(500, {"error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, {"error": "JSON invalido"})
            return

        if self.path == "/print":
            cfg = load_config()
            printer = body.get("printer") or cfg.get("printer", "")
            texto = body.get("texto", "")
            if not printer:
                self._send(400, {"ok": False, "error": "Sin impresora configurada"})
                return
            try:
                print_raw(texto, printer)
                resp = {"ok": True}
                if body.get("diag"):
                    resp["diag"] = diagnostico(printer)
                self._send(200, resp)
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif self.path == "/print-label":
            cfg = load_config()
            printer = body.get("printer") or cfg.get("printer_etiquetas", "")
            imagen_base64 = body.get("imagen_base64", "")
            if not printer:
                self._send(400, {"ok": False, "error": "Sin impresora de etiquetas configurada"})
                return
            if not imagen_base64:
                self._send(400, {"ok": False, "error": "Sin imagen"})
                return
            try:
                print_image(imagen_base64, printer)
                resp = {"ok": True}
                if body.get("diag"):
                    resp["diag"] = diagnostico(printer)
                self._send(200, resp)
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif self.path == "/config":
            cfg = load_config()
            if "printer" in body:
                cfg["printer"] = body["printer"].strip()
            if "printer_etiquetas" in body:
                cfg["printer_etiquetas"] = body.get("printer_etiquetas", "").strip()
            save_config(cfg)
            self._send(200, {"ok": True})

        else:
            self.send_response(404)
            self.end_headers()


def _crear_icono():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (64, 64), "#1a1a2e")
    d = ImageDraw.Draw(img)
    # Cuerpo de impresora
    d.rectangle([10, 22, 54, 40], fill="#3A86FF")
    # Bandeja de papel (arriba)
    d.rectangle([18, 14, 46, 24], fill="#e5e7eb")
    # Papel saliendo (abajo)
    d.rectangle([18, 37, 46, 52], fill="#e5e7eb")
    # Líneas del papel
    d.rectangle([22, 41, 42, 43], fill="#9ca3af")
    d.rectangle([22, 46, 38, 48], fill="#9ca3af")
    # Luz indicadora
    d.ellipse([44, 26, 51, 33], fill="#06D6A0")
    return img


def _label_status(item):
    cfg = load_config()
    t = cfg.get("printer") or "sin config"
    e = cfg.get("printer_etiquetas") or "sin config"
    return f"Tickets: {t}  |  Etiquetas: {e}"


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()

    try:
        import pystray

        def on_salir(icon, _):
            icon.stop()
            server.shutdown()

        icono = pystray.Icon(
            "pos_agent",
            _crear_icono(),
            "POS Agent — activo",
            pystray.Menu(
                pystray.MenuItem(_label_status, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", on_salir),
            ),
        )
        icono.run()

    except Exception:
        # Fallback si pystray falla: correr sin bandeja
        hilo.join()
