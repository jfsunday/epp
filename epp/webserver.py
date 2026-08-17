"""Built-in webserver for E++."""

from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .builtins import format_value


def _to_json(value: object) -> object:
    """Convert E++ value to JSON-serializable Python value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value == int(value) else value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    return str(value)


class EppWebserver:
    """Simple HTTP server that dispatches to E++ handler functions."""

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.routes: dict[tuple[str, str], str] = {}
        self.server: HTTPServer | None = None
        self._lock = threading.Lock()

    def add_route(self, method: str, path: str, handler_name: str) -> None:
        self.routes[(method.upper(), path)] = handler_name

    def start(self, port: int) -> None:
        webserver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                webserver._handle(self, "GET")

            def do_POST(self):
                webserver._handle(self, "POST")

            def do_PUT(self):
                webserver._handle(self, "PUT")

            def do_DELETE(self):
                webserver._handle(self, "DELETE")

            def log_message(self, format, *args):
                pass  # suppress default logging

        self.server = HTTPServer(("", port), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.interpreter._say_fn(f"Webserver running on port {port}")

    def _handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        parsed = urlparse(handler.path)
        path = parsed.path
        key = (method, path)

        if key not in self.routes:
            handler.send_response(404)
            handler.send_header("Content-Type", "text/plain")
            handler.end_headers()
            handler.wfile.write(b"Not Found")
            return

        fn_name = self.routes[key]

        # Build request dict
        request: dict[str, object] = {
            "method": method,
            "path": path,
        }

        # Query parameters
        params = parse_qs(parsed.query)
        for k, v in params.items():
            request[k] = v[0] if len(v) == 1 else v

        # Body for POST/PUT
        if method in ("POST", "PUT"):
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length:
                body = handler.rfile.read(content_length).decode()
                request["body"] = body
                try:
                    request["data"] = json.loads(body)
                except (json.JSONDecodeError, ValueError):
                    pass

        with self._lock:
            self.interpreter._web_response = None
            self.interpreter._web_status = 200
            try:
                self.interpreter.call_function_with_values(fn_name, [request])
            except Exception as e:
                handler.send_response(500)
                handler.send_header("Content-Type", "text/plain")
                handler.end_headers()
                handler.wfile.write(str(e).encode())
                return

            response = self.interpreter._web_response
            status = self.interpreter._web_status

        if response is None:
            response = ""

        # Serialize response
        if isinstance(response, (dict, list)):
            content_type = "application/json"
            body_bytes = json.dumps(_to_json(response)).encode()
        else:
            content_type = "text/plain"
            body_bytes = format_value(response).encode()

        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body_bytes)))
        handler.end_headers()
        handler.wfile.write(body_bytes)

    def wait(self) -> None:
        if self.server is None:
            return
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.server.shutdown()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
