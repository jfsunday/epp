"""Tests for E++ webserver extensions (CORS, path params, content type, static)."""

import json
import os
import time
import urllib.request
import urllib.error


class TestPathParams:
    def test_path_param_route(self, run):
        interp, out = run("""
Define handle user that takes request,
    Let id be the path parameter id of request.
    Respond with the value of id.
End define.

Start a webserver on port 9876.
Add route GET slash users slash param id to handle user.
""")
        ws = interp._webserver
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9876/users/42")
        assert resp.read() == b"42"
        ws.stop()


class TestQueryParams:
    def test_query_param(self, run):
        interp, out = run("""
Define handle search that takes request,
    Let q be the query parameter q of request.
    Respond with the value of q.
End define.

Start a webserver on port 9877.
Add route GET slash search to handle search.
""")
        ws = interp._webserver
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9877/search?q=hello")
        assert resp.read() == b"hello"
        ws.stop()


class TestCORS:
    def test_cors_headers(self, run):
        interp, out = run("""
Define handle home that takes request,
    Respond with ok.
End define.

Start a webserver on port 9878.
Enable CORS.
Add route GET slash to handle home.
""")
        ws = interp._webserver
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9878/")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        ws.stop()


class TestContentType:
    def test_custom_content_type(self, run):
        interp, out = run("""
Define handle html that takes request,
    Set content type to text slash html.
    Respond with hello.
End define.

Start a webserver on port 9879.
Add route GET slash to handle html.
""")
        ws = interp._webserver
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9879/")
        assert "text/html" in resp.headers.get("Content-Type")
        ws.stop()


class TestStaticFiles:
    def test_static_serving(self, run):
        import tempfile, shutil
        d = "eppstatic"
        os.makedirs(d, exist_ok=True)
        try:
            with open(os.path.join(d, "hello.txt"), "w") as f:
                f.write("static content")
            interp, out = run("""
Start a webserver on port 9880.
Serve static files from the folder eppstatic.
""")
            ws = interp._webserver
            time.sleep(0.1)
            resp = urllib.request.urlopen("http://localhost:9880/hello.txt")
            assert resp.read() == b"static content"
            ws.stop()
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestRequestBody:
    def test_post_body(self, run):
        interp, out = run("""
Define handle post that takes request,
    Let data be the body of request.
    Respond with the value of data.
End define.

Start a webserver on port 9881.
Add route POST slash data to handle post.
""")
        ws = interp._webserver
        time.sleep(0.1)
        req = urllib.request.Request(
            "http://localhost:9881/data",
            data=json.dumps({"key": "value"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req)
        body = json.loads(resp.read())
        assert body["key"] == "value"
        ws.stop()
