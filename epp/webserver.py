"""Built-in webserver for E++."""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from .builtins import format_value

# Maximum accepted request body size (25 MB)
MAX_BODY_SIZE = 25 * 1024 * 1024

# Name of the cookie carrying the server side session id
SESSION_COOKIE = "epp_session"


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


def _parse_cookie_header(raw: str | None) -> dict[str, str]:
    """Parse a raw Cookie header into a plain {name: value} dict."""
    cookies: dict[str, str] = {}
    if not raw:
        return cookies
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return cookies
    for name, morsel in jar.items():
        cookies[name] = morsel.value
    return cookies


def _disposition_param(header: str, key: str) -> str | None:
    """Read a single parameter (e.g. name / filename) from a header line."""
    for part in header.split(";")[1:]:
        part = part.strip()
        if "=" not in part:
            continue
        raw_key, _, raw_value = part.partition("=")
        if raw_key.strip().lower() == key:
            return raw_value.strip().strip('"')
    return None


def _boundary_of(content_type: str) -> str | None:
    """Extract the multipart boundary from a Content-Type header."""
    for part in content_type.split(";")[1:]:
        part = part.strip()
        if part.lower().startswith("boundary="):
            value = part[len("boundary="):].strip()
            return value.strip('"') or None
    return None


def _parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], dict[str, dict]]:
    """Parse a multipart/form-data body into (form fields, uploaded files).

    Implemented by hand because the `cgi` module is gone in Python 3.13+.
    """
    form: dict[str, str] = {}
    files: dict[str, dict] = {}
    boundary = _boundary_of(content_type)
    if not boundary:
        return form, files

    delimiter = b"--" + boundary.encode("latin-1")
    for chunk in body.split(delimiter):
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if not chunk or chunk.startswith(b"--"):
            continue  # preamble or closing delimiter
        if b"\r\n\r\n" not in chunk:
            continue
        raw_headers, _, content = chunk.partition(b"\r\n\r\n")
        if content.endswith(b"\r\n"):
            content = content[:-2]

        headers: dict[str, str] = {}
        for line in raw_headers.decode("utf-8", "replace").split("\r\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                headers[key.strip().lower()] = value.strip()

        disposition = headers.get("content-disposition", "")
        name = _disposition_param(disposition, "name")
        if name is None:
            continue
        filename = _disposition_param(disposition, "filename")
        if filename is None:
            form[name] = content.decode("utf-8", "replace")
        else:
            files[name] = {
                "filename": filename,
                "content": content,
                "content type": headers.get("content-type", "application/octet-stream"),
            }
    return form, files


class EppWebserver:
    """Simple HTTP server that dispatches to E++ handler functions."""

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.routes: list[tuple[str, str, str, list[str]]] = []
        self.server: HTTPServer | None = None
        self._lock = threading.Lock()
        self._cors = False
        self._static_folder: str | None = None
        self._sessions: dict[str, dict] = {}
        self._session_lock = threading.Lock()
        self._middleware = None
        self._websockets = None

    def add_route(self, method: str, path: str, handler_name: str, params: list[str] | None = None) -> None:
        self.routes.append((method.upper(), path, handler_name, params or []))

    def enable_cors(self) -> None:
        self._cors = True

    def set_static_folder(self, folder: str) -> None:
        self._static_folder = folder

    def set_middleware(self, fn) -> None:
        """Register a callable fn(request) that runs before every route handler."""
        self._middleware = fn

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def _lookup_session(self, sid: str | None) -> dict | None:
        if not sid:
            return None
        with self._session_lock:
            return self._sessions.get(sid)

    def start_session(self, request: dict) -> dict:
        """Return the session for *request*, creating one if necessary."""
        cookies = request.get("__cookies")
        sid = cookies.get(SESSION_COOKIE) if isinstance(cookies, dict) else None
        if not sid:
            known = request.get("__session_id")
            sid = known if isinstance(known, str) else None

        session = self._lookup_session(sid)
        if session is not None:
            request["__session"] = session
            request["__session_id"] = sid
            return session

        sid = secrets.token_urlsafe(24)
        session = {}
        with self._session_lock:
            self._sessions[sid] = session
        request["__session"] = session
        request["__session_id"] = sid

        cookies_out = getattr(self.interpreter, "_web_cookies", None)
        if cookies_out is None:
            cookies_out = []
            self.interpreter._web_cookies = cookies_out
        cookies_out.append((SESSION_COOKIE, sid))
        return session

    # ------------------------------------------------------------------
    # Websockets
    # ------------------------------------------------------------------

    def _get_hub(self):
        """Create the websocket hub on first use (lazy import)."""
        if self._websockets is None:
            from .websocket import WebsocketHub
            self._websockets = WebsocketHub(self.interpreter)
        return self._websockets

    def get_websocket_hub(self):
        return self._get_hub()

    def add_websocket_route(self, path: str, handler_name: str) -> None:
        self._get_hub().add_route(path, handler_name)

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

        # Websocket upgrade takes precedence over everything else
        if method == "GET" and self._websockets is not None:
            hub = self._websockets
            if hub.has_route(path):
                if hub.handle_upgrade(handler, path):
                    return

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

        # Cookies
        cookies = _parse_cookie_header(handler.headers.get("Cookie"))
        request["__cookies"] = cookies

        # Existing session (do not create a new one here)
        sid = cookies.get(SESSION_COOKIE)
        session = self._lookup_session(sid)
        if session is not None:
            request["__session"] = session
            request["__session_id"] = sid

        # Form fields and uploads are always present, even when empty
        request["__form"] = {}
        request["__files"] = {}

        # Body for POST/PUT
        if method in ("POST", "PUT"):
            try:
                content_length = int(handler.headers.get("Content-Length", 0) or 0)
            except ValueError:
                content_length = 0
            if content_length > MAX_BODY_SIZE:
                handler.close_connection = True
                handler.send_response(413)
                if self._cors:
                    self._add_cors_headers(handler)
                handler.send_header("Content-Type", "text/plain")
                handler.end_headers()
                handler.wfile.write(b"Payload Too Large")
                return
            if content_length:
                raw_body = handler.rfile.read(content_length)
                raw_content_type = handler.headers.get("Content-Type", "") or ""
                base_type = raw_content_type.split(";")[0].strip().lower()
                if base_type == "multipart/form-data":
                    form, files = _parse_multipart(raw_body, raw_content_type)
                    request["__form"] = form
                    request["__files"] = files
                else:
                    body = raw_body.decode("utf-8", "replace")
                    request["body"] = body
                    if base_type == "application/x-www-form-urlencoded":
                        request["__form"] = {
                            k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items() if v
                        }
                    try:
                        request["data"] = json.loads(body)
                    except (json.JSONDecodeError, ValueError):
                        pass

        with self._lock:
            self.interpreter._web_response = None
            self.interpreter._web_status = 200
            self.interpreter._web_content_type = None
            self.interpreter._web_cookies = []
            try:
                if self._middleware is not None:
                    self._middleware(request)
                if self.interpreter._web_response is None:
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
            response_cookies = list(getattr(self.interpreter, "_web_cookies", None) or [])

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
        for cookie_name, cookie_value in response_cookies:
            handler.send_header("Set-Cookie", f"{cookie_name}={cookie_value}; Path=/")
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
        if self._websockets is not None:
            try:
                self._websockets.close_all()
            except Exception:
                pass
        if self.server:
            self.server.shutdown()
