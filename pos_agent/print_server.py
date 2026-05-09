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
                self._send(200, {"ok": True})
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
                self._send(200, {"ok": True})
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
