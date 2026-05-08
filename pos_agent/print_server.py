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
        return {"printer": ""}


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
            self._send(200, {"ok": True, "printer": cfg.get("printer", "")})
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

        elif self.path == "/config":
            printer = body.get("printer", "").strip()
            save_config({"printer": printer})
            self._send(200, {"ok": True})

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    cfg = load_config()
    print(f"[POS Agent] Corriendo en localhost:{PORT}")
    print(f"[POS Agent] Impresora: {cfg.get('printer') or '(no configurada)'}")
    print("[POS Agent] Minimiza esta ventana — no la cierres.")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[POS Agent] Detenido.")
