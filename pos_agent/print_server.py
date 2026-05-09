import base64
import io
import json
import os
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

    # Leer DPI embebido por python-barcode (203 o 300 según preset)
    img_dpi = img.info.get("dpi", (203, 203))
    if isinstance(img_dpi, (int, float)):
        img_dpi = (img_dpi, img_dpi)
    dpi_x, dpi_y = max(float(img_dpi[0]), 1.0), max(float(img_dpi[1]), 1.0)

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    pdc = win32ui.CreateDC()
    pdc.CreatePrinterDC(printer_name)

    # Densidad real de la impresora
    printer_dpi_x = pdc.GetDeviceCaps(win32con.LOGPIXELSX)
    printer_dpi_y = pdc.GetDeviceCaps(win32con.LOGPIXELSY)
    printer_w = pdc.GetDeviceCaps(win32con.HORZRES)
    printer_h = pdc.GetDeviceCaps(win32con.VERTRES)

    img_w, img_h = img.size

    # Tamaño de salida que preserva el tamaño físico real de la etiqueta
    out_w = int(img_w * printer_dpi_x / dpi_x)
    out_h = int(img_h * printer_dpi_y / dpi_y)

    # Solo reducir si excede el área imprimible (no escalar hacia arriba)
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


if __name__ == "__main__":
    cfg = load_config()
    print(f"[POS Agent] Corriendo en localhost:{PORT}")
    print(f"[POS Agent] Impresora tickets : {cfg.get('printer') or '(no configurada)'}")
    print(f"[POS Agent] Impresora etiquetas: {cfg.get('printer_etiquetas') or '(no configurada)'}")
    print("[POS Agent] Minimiza esta ventana — no la cierres.")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[POS Agent] Detenido.")
