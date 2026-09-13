"""Functional tests for cookies, sessions, forms, uploads and middleware.

These start a real E++ webserver and talk to it over HTTP.
"""

import http.cookiejar
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

from epp import run_source

PORT = 8973
BASE = f"http://127.0.0.1:{PORT}"

SOURCE = f"""
Let visits be 0.

Before every request, do the following.
Add 1 to visits.
End before.

Define handle login that takes request, do the following.
Let user be the form value username of request.
Start a session for request.
Set the session value name in request to the value of user.
Set the cookie username of request to the value of user.
Respond with welcome.
End define.

Define handle me that takes request, do the following.
Create a dictionary called answer.
Set the entry session in answer to the session value name of request.
Set the entry cookie in answer to the cookie username of request.
Set the entry visits in answer to the value of visits.
Respond with the value of answer.
End define.

Define handle upload that takes request, do the following.
Let data be the uploaded file avatar of request.
Write the value of data to the file uploadedtest.
Respond with saved.
End define.

Add route POST slash login to handle login.
Add route GET slash me to handle me.
Add route POST slash upload to handle upload.
Start a webserver on port {PORT}.
"""


@pytest.fixture(scope="module")
def server():
    thread = threading.Thread(target=run_source, args=(SOURCE,), daemon=True)
    thread.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{BASE}/me", timeout=0.5).read()
            break
        except urllib.error.HTTPError:
            break
        except OSError:
            time.sleep(0.1)
    yield
    if os.path.exists("uploadedtest"):
        os.remove("uploadedtest")


@pytest.fixture
def client(server):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return opener, jar


class TestSessionsAndCookies:
    def test_login_sets_session_and_cookie(self, client):
        opener, jar = client
        body = opener.open(f"{BASE}/login", data=b"username=Alice").read()
        assert body == b"welcome"
        names = {cookie.name for cookie in jar}
        assert "epp_session" in names
        assert "username" in names

    def test_session_and_cookie_survive_the_next_request(self, client):
        opener, _ = client
        opener.open(f"{BASE}/login", data=b"username=Bob").read()
        import json
        answer = json.loads(opener.open(f"{BASE}/me").read())
        assert answer["session"] == "Bob"
        assert answer["cookie"] == "Bob"

    def test_middleware_runs_before_every_request(self, client):
        import json
        opener, _ = client
        opener.open(f"{BASE}/login", data=b"username=Carol").read()
        first = json.loads(opener.open(f"{BASE}/me").read())["visits"]
        second = json.loads(opener.open(f"{BASE}/me").read())["visits"]
        assert second == first + 1


class TestUploads:
    def test_uploaded_bytes_are_written_unchanged(self, client):
        opener, _ = client
        boundary = "----epptest"
        content = b"\x00\x01BINARY\xff"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="avatar"; '
            f'filename="a.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            f"{BASE}/upload", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        assert opener.open(request).read() == b"saved"
        with open("uploadedtest", "rb") as handle:
            assert handle.read() == content
