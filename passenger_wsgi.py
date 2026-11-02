"""
Punto de Entrada WSGI / ASGI para GoDaddy Hosting (cPanel "Setup Python App" / Phusion Passenger).
Compatible automáticamente con:
- GoDaddy cPanel (Phusion Passenger WSGI -> FastAPI ASGI)
- Gunicorn / Uvicorn en GoDaddy VPS
- Base de Datos SQLite embebida (sanbao_dev.db), MySQL/MariaDB cPanel o PostgreSQL.
"""
import asyncio
import io
import os
import sys
from urllib.parse import unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app as fastapi_app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.init_db import init_db  # noqa: E402

_DB_INITIALIZED = False


def _ensure_db_initialized():
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    db = SessionLocal()
    try:
        init_db(db)
        _DB_INITIALIZED = True
    except Exception:
        pass
    finally:
        db.close()


_ensure_db_initialized()


class _BuiltinASGIMiddleware:
    """Adaptador WSGI -> ASGI puro en Python para Phusion Passenger en GoDaddy cPanel."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        _ensure_db_initialized()

        method = environ.get("REQUEST_METHOD", "GET").upper()
        script_name = environ.get("SCRIPT_NAME", "")
        path_info = environ.get("PATH_INFO", "/")
        query_string = environ.get("QUERY_STRING", "").encode("latin-1")

        # Construir cabeceras HTTP para el scope ASGI
        headers = []
        if environ.get("CONTENT_TYPE"):
            headers.append((b"content-type", environ["CONTENT_TYPE"].encode("latin-1")))
        if environ.get("CONTENT_LENGTH"):
            headers.append((b"content-length", environ["CONTENT_LENGTH"].encode("latin-1")))

        for key, val in environ.items():
            if key.startswith("HTTP_"):
                hdr_name = key[5:].replace("_", "-").lower().encode("latin-1")
                headers.append((hdr_name, str(val).encode("latin-1")))

        body_stream = environ.get("wsgi.input") or io.BytesIO()
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            content_length = 0
        request_body = body_stream.read(content_length) if content_length > 0 else b""

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.1"},
            "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[-1],
            "method": method,
            "scheme": environ.get("wsgi.url_scheme", "http"),
            "path": unquote(path_info) or "/",
            "raw_path": path_info.encode("latin-1", errors="ignore"),
            "query_string": query_string,
            "root_path": script_name,
            "headers": headers,
            "client": (environ.get("REMOTE_ADDR", "127.0.0.1"), int(environ.get("REMOTE_PORT") or 0)),
            "server": (environ.get("SERVER_NAME", "localhost"), int(environ.get("SERVER_PORT") or 80)),
        }

        status_code = 200
        response_headers = []
        body_chunks = []
        body_sent = False

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": request_body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal status_code, response_headers
            msg_type = message.get("type")
            if msg_type == "http.response.start":
                status_code = message.get("status", 200)
                raw_headers = message.get("headers", [])
                response_headers = [
                    (k.decode("latin-1"), v.decode("latin-1")) for k, v in raw_headers
                ]
            elif msg_type == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.asgi_app(scope, receive, send))
        finally:
            loop.close()

        status_map = {
            200: "200 OK",
            201: "201 Created",
            204: "204 No Content",
            301: "301 Moved Permanently",
            302: "302 Found",
            307: "307 Temporary Redirect",
            400: "400 Bad Request",
            401: "401 Unauthorized",
            403: "403 Forbidden",
            404: "404 Not Found",
            422: "422 Unprocessable Entity",
            500: "500 Internal Server Error",
        }
        status_line = status_map.get(status_code, f"{status_code} OK")
        start_response(status_line, response_headers)
        return [b"".join(body_chunks)]


try:
    from a2wsgi import ASGIMiddleware  # type: ignore

    application = ASGIMiddleware(fastapi_app)
except ImportError:
    application = _BuiltinASGIMiddleware(fastapi_app)
