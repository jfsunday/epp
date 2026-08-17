"""Tests for E++ webserver."""

import json
import time
import urllib.request

import pytest


class TestWebserver:
    def test_start_and_route(self, run):
        interp, out = run("""
Define handle home that takes request,
    Respond with Hello World.
End define.

Start a webserver on port 9871.
Add route GET slash to handle home.
""")
        ws = interp._webserver
        assert ws is not None
        assert any(m == "GET" and p == "/" for m, p, *_ in ws.routes)

        # Make a real HTTP request
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9871/")
        assert resp.read() == b"Hello World"
        ws.stop()

    def test_json_response(self, run):
        interp, out = run("""
Define handle api that takes request,
    Create a dictionary called data.
    Set the entry status in data to ok.
    Set the entry count in data to 42.
    Respond with the value of data.
End define.

Start a webserver on port 9872.
Add route GET slash api to handle api.
""")
        ws = interp._webserver
        time.sleep(0.1)
        resp = urllib.request.urlopen("http://localhost:9872/api")
        body = json.loads(resp.read())
        assert body["status"] == "ok"
        assert body["count"] == 42
        ws.stop()

    def test_404(self, run):
        interp, out = run("""
Define handle home that takes request,
    Respond with ok.
End define.

Start a webserver on port 9873.
Add route GET slash to handle home.
""")
        ws = interp._webserver
        time.sleep(0.1)
        try:
            urllib.request.urlopen("http://localhost:9873/missing")
            assert False, "should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 404
        ws.stop()

    def test_route_parsing(self, run):
        interp, out = run("""
Define handler that takes request,
    Respond with ok.
End define.

Start a webserver on port 9874.
Add route GET slash api slash users to handler.
""")
        ws = interp._webserver
        assert any(m == "GET" and p == "/api/users" for m, p, *_ in ws.routes)
        ws.stop()


class TestRespondWithStatus:
    def test_custom_status(self, run):
        interp, out = run("""
Define handle err that takes request,
    Respond with not allowed and status 403.
End define.

Start a webserver on port 9875.
Add route GET slash err to handle err.
""")
        ws = interp._webserver
        time.sleep(0.1)
        try:
            urllib.request.urlopen("http://localhost:9875/err")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 403
        ws.stop()
