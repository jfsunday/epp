"""Built-in webserver for E++."""

from __future__ import annotations

import json
import mimetypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from .builtins import format_value


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


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
        self.routes: list[tuple[str, str, str, list[str]]] = []
        self.server: HTTPServer | None = None
        self._lock = threading.Lock()
        self._cors = False
        self._static_folder: str | None = None

    def add_route(self, method: str, path: str, handler_name: str, params: list[str] | None = None) -> None:
        self.routes.append((method.upper(), path, handler_name, params or []))

    def enable_cors(self) -> None:
        self._cors = True

    def set_static_folder(self, folder: str) -> None:
        self._static_folder = folder

    def _match_route(self, method: str, path: str) -> tuple[str | None, dict[str, str]]:
        """Match request to a route, supporting path parameters."""
        for route_method, route_path, handler_name, params in self.routes:
            if route_method != method:
                continue
            if not params:
                if route_path == path:
                    return handler_name, {}
                continue
            # Pattern match with params
            route_parts = route_path.split("/")
            path_parts = path.split("/")
            if len(route_parts) != len(path_parts):
                continue
            param_values: dict[str, str] = {}
            match = True
            for rp, pp in zip(route_parts, path_parts):
                if rp.startswith(":"):
                    param_values[rp[1:]] = pp
                elif rp != pp:
                    match = False
                    break
            if match:
                return handler_name, param_values
        return None, {}

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

            def do_OPTIONS(self):
                webserver._handle(self, "OPTIONS")

            def log_message(self, format, *args):
                pass  # suppress default logging

        self.server = _ThreadedHTTPServer(("", port), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.interpreter._say_fn(f"Webserver running on port {port}")

    def _add_cors_headers(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _serve_static(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Try to serve a static file. Returns True if served."""
        if self._static_folder is None:
            return False
        # Remove leading slash
        rel_path = path.lstrip("/")
        if not rel_path:
            rel_path = "index.html"
        file_path = os.path.join(self._static_folder, rel_path)
        if not os.path.isfile(file_path):
            return False
        # Security: ensure path doesn't escape static folder
        abs_static = os.path.abspath(self._static_folder)
        abs_file = os.path.abspath(file_path)
        if not abs_file.startswith(abs_static):
            return False
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = "application/octet-stream"
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except OSError:
            return False
        handler.send_response(200)
        if self._cors:
            self._add_cors_headers(handler)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return True

    def _handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        parsed = urlparse(handler.path)
        path = parsed.path

        # Handle CORS preflight
        if method == "OPTIONS" and self._cors:
            handler.send_response(204)
            self._add_cors_headers(handler)
            handler.end_headers()
            return

        fn_name, path_params = self._match_route(method, path)

        if fn_name is None:
            # Try static files
            if method == "GET" and self._serve_static(handler, path):
                return
            handler.send_response(404)
            if self._cors:
                self._add_cors_headers(handler)
            handler.send_header("Content-Type", "text/plain")
            handler.end_headers()
            handler.wfile.write(b"Not Found")
            return

        # Build request dict
        request: dict[str, object] = {
            "method": method,
            "path": path,
        }

        # Path parameters
        if path_params:
            request["__path_params"] = path_params

        # Query parameters
        query_params = parse_qs(parsed.query)
        flat_query: dict[str, str] = {}
        for k, v in query_params.items():
            val = v[0] if len(v) == 1 else v
            request[k] = val
            flat_query[k] = val if isinstance(val, str) else v[0]
        request["__query_params"] = flat_query

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
            self.interpreter._web_content_type = None
            try:
                self.interpreter.call_function_with_values(fn_name, [request])
            except Exception as e:
                error_msg = str(e)
                response = None
                status = 500
                custom_content_type = None
                # Send error response outside lock below
                handler.send_response(500)
                if self._cors:
                    self._add_cors_headers(handler)
                handler.send_header("Content-Type", "text/plain")
                handler.end_headers()
                handler.wfile.write(error_msg.encode())
                return

            response = self.interpreter._web_response
            status = self.interpreter._web_status
            custom_content_type = self.interpreter._web_content_type

        if response is None:
            response = ""

        # Serialize response
        if custom_content_type:
            content_type = custom_content_type
            if isinstance(response, (dict, list)):
                body_bytes = json.dumps(_to_json(response)).encode()
            else:
                body_bytes = format_value(response).encode()
        elif isinstance(response, (dict, list)):
            content_type = "application/json"
            body_bytes = json.dumps(_to_json(response)).encode()
        else:
            content_type = "text/plain"
            body_bytes = format_value(response).encode()

        handler.send_response(status)
        if self._cors:
            self._add_cors_headers(handler)
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
