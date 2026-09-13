"""Minimal RFC 6455 WebSocket server for E++.

Hooks into an existing BaseHTTPRequestHandler via socket-hijacking after
the HTTP Upgrade handshake. No external dependencies — pure stdlib only.
"""

from __future__ import annotations

import hashlib
import base64
import struct
import threading
from http.server import BaseHTTPRequestHandler
from typing import Optional

# Magic string defined by RFC 6455
_WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Maximum allowed payload per message (10 MB)
_MAX_PAYLOAD = 10 * 1024 * 1024

# Opcodes
_OP_CONTINUATION = 0x0
_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA


def _accept_key(client_key: str) -> str:
    """Compute Sec-WebSocket-Accept value per RFC 6455 §4.2.2."""
    combined = (client_key.strip() + _WS_MAGIC).encode("latin-1")
    digest = hashlib.sha1(combined).digest()
    return base64.b64encode(digest).decode("ascii")


def _send_frame(sock, opcode: int, payload: bytes) -> None:
    """Write a single unmasked server frame to *sock*."""
    length = len(payload)
    # First byte: FIN=1, RSV=0, opcode
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    if length < 126:
        header.append(length)
    elif length <= 0xFFFF:
        header.append(126)
        header += struct.pack("!H", length)
    else:
        header.append(127)
        header += struct.pack("!Q", length)
    sock.sendall(bytes(header) + payload)


def _read_exact(sock, n: int) -> Optional[bytes]:
    """Read exactly *n* bytes from *sock*. Returns None on short read / error."""
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except OSError:
            return None
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def _read_frame(sock):
    """Read one WebSocket frame.

    Returns (fin, opcode, payload_bytes) or raises ConnectionError on
    protocol violation / connection drop.
    """
    header = _read_exact(sock, 2)
    if header is None:
        raise ConnectionError("connection closed")

    b0, b1 = header[0], header[1]
    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F

    if length == 126:
        ext = _read_exact(sock, 2)
        if ext is None:
            raise ConnectionError("truncated length")
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = _read_exact(sock, 8)
        if ext is None:
            raise ConnectionError("truncated length")
        length = struct.unpack("!Q", ext)[0]

    if length > _MAX_PAYLOAD:
        raise ConnectionError(f"payload too large: {length}")

    mask_key = b""
    if masked:
        mask_key = _read_exact(sock, 4)
        if mask_key is None:
            raise ConnectionError("truncated mask key")

    payload_raw = _read_exact(sock, length)
    if payload_raw is None:
        raise ConnectionError("truncated payload")

    if masked:
        payload = bytearray(payload_raw)
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
        payload = bytes(payload)
    else:
        payload = payload_raw

    return fin, opcode, payload


class _Connection:
    """Internal per-connection state."""

    def __init__(self, conn_id: int, sock, path: str):
        self.conn_id = conn_id
        self.sock = sock
        self.path = path
        self.lock = threading.Lock()
        self.closed = False

    def send_text(self, text: str) -> None:
        data = text.encode("utf-8")
        with self.lock:
            if self.closed:
                return
            try:
                _send_frame(self.sock, _OP_TEXT, data)
            except OSError:
                self.closed = True

    def send_close(self) -> None:
        with self.lock:
            if self.closed:
                return
            try:
                _send_frame(self.sock, _OP_CLOSE, b"")
            except OSError:
                pass
            self.closed = True

    def send_pong(self, payload: bytes) -> None:
        with self.lock:
            if self.closed:
                return
            try:
                _send_frame(self.sock, _OP_PONG, payload)
            except OSError:
                self.closed = True

    def as_dict(self) -> dict:
        return {"id": self.conn_id, "path": self.path}


class WebsocketHub:
    """Registry of WebSocket routes; performs upgrade and serves connections."""

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self._routes: dict[str, str] = {}          # path -> handler_name
        self._connections: dict[int, _Connection] = {}
        self._conn_lock = threading.Lock()
        self._next_id = 0

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def add_route(self, path: str, handler_name: str) -> None:
        """Register an E++ handler function name for a websocket path."""
        self._routes[path] = handler_name

    def has_route(self, path: str) -> bool:
        return path in self._routes

    # ------------------------------------------------------------------
    # Upgrade & serve
    # ------------------------------------------------------------------

    def handle_upgrade(self, http_handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Perform WebSocket handshake and serve the connection.

        Returns True if this request was taken over (caller must not send
        any further HTTP response). Returns False if this is not a WebSocket
        upgrade request for a known route.
        """
        if path not in self._routes:
            return False

        headers = http_handler.headers
        upgrade_header = headers.get("Upgrade", "")
        if upgrade_header.lower() != "websocket":
            return False

        ws_key = headers.get("Sec-WebSocket-Key")
        if not ws_key:
            return False

        handler_name = self._routes[path]

        # --- Send 101 Switching Protocols ---
        accept = _accept_key(ws_key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        try:
            http_handler.wfile.write(response.encode("latin-1"))
            http_handler.wfile.flush()
        except OSError:
            return True  # Request was ours but socket died immediately

        # Grab the raw socket
        sock = http_handler.connection

        # Register connection
        with self._conn_lock:
            conn_id = self._next_id
            self._next_id += 1
            conn = _Connection(conn_id, sock, path)
            self._connections[conn_id] = conn

        conn_dict = conn.as_dict()

        # --- Serve loop ---
        # Accumulate fragments here
        fragmented_opcode: Optional[int] = None
        fragmented_chunks: list[bytes] = []

        try:
            while True:
                try:
                    fin, opcode, payload = _read_frame(sock)
                except ConnectionError:
                    break
                except (OSError, ConnectionResetError):
                    break

                # Control frames (must not be fragmented per RFC)
                if opcode == _OP_CLOSE:
                    conn.send_close()
                    break
                elif opcode == _OP_PING:
                    conn.send_pong(payload)
                    continue
                elif opcode == _OP_PONG:
                    # unsolicited pong — ignore
                    continue

                # Data frames
                if opcode == _OP_CONTINUATION:
                    if fragmented_opcode is None:
                        # Protocol error: continuation without start frame
                        conn.send_close()
                        break
                    fragmented_chunks.append(payload)
                    if fin:
                        full_payload = b"".join(fragmented_chunks)
                        orig_opcode = fragmented_opcode
                        fragmented_opcode = None
                        fragmented_chunks = []
                        self._dispatch(handler_name, conn_dict, orig_opcode, full_payload, conn)
                elif opcode in (_OP_TEXT, _OP_BINARY):
                    if fin:
                        # Single-frame message
                        self._dispatch(handler_name, conn_dict, opcode, payload, conn)
                    else:
                        # Start of fragmented message
                        if fragmented_opcode is not None:
                            # Protocol error: new message while previous unfinished
                            conn.send_close()
                            break
                        fragmented_opcode = opcode
                        fragmented_chunks = [payload]
                else:
                    # Unknown opcode — ignore
                    pass
        finally:
            conn.closed = True
            with self._conn_lock:
                self._connections.pop(conn_id, None)

        return True

    # ------------------------------------------------------------------
    # Dispatch to E++ handler
    # ------------------------------------------------------------------

    def _dispatch(self, handler_name: str, conn_dict: dict, opcode: int, payload: bytes, conn: _Connection) -> None:
        if opcode == _OP_TEXT:
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                text = payload.decode("latin-1")
        else:
            # Binary: pass as latin-1 string so E++ code can see raw bytes
            text = payload.decode("latin-1")

        try:
            self.interpreter.call_websocket_handler(handler_name, conn_dict, text)
        except Exception as exc:
            try:
                self.interpreter._say_fn(f"[websocket] handler error: {exc}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Send / broadcast
    # ------------------------------------------------------------------

    def send(self, connection: object, text: str) -> None:
        """Send *text* to a single connection.

        *connection* may be the dict handed to E++ code, or an int id.
        Silently ignores closed / unknown connections.
        """
        if isinstance(connection, dict):
            conn_id = connection.get("id")
        elif isinstance(connection, (int, float)):
            conn_id = int(connection)
        else:
            return
        with self._conn_lock:
            conn = self._connections.get(conn_id)
        if conn is None:
            return
        conn.send_text(text)

    def broadcast(self, text: str) -> None:
        """Send *text* to every open connection."""
        with self._conn_lock:
            conns = list(self._connections.values())
        for conn in conns:
            conn.send_text(text)

    def close_all(self) -> None:
        """Close every open connection."""
        with self._conn_lock:
            conns = list(self._connections.values())
        for conn in conns:
            conn.send_close()
        with self._conn_lock:
            self._connections.clear()
