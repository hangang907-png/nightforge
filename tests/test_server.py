import hashlib
import hmac
import io
import json

from nightforge.server import create_wsgi_app


def test_wsgi_receiver_accepts_signed_ping(tmp_path):
    payload = b'{"zen":"keep it logically awesome"}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    app = create_wsgi_app("secret", "owner/repo", tmp_path)
    status = []
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/webhook",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "HTTP_X_GITHUB_DELIVERY": "ping-1",
        "HTTP_X_GITHUB_EVENT": "ping",
        "HTTP_X_HUB_SIGNATURE_256": signature,
    }

    body = b"".join(app(environ, lambda value, headers: status.append((value, headers))))

    assert status[0][0] == "202 Accepted"
    assert json.loads(body)["accepted"] is True
