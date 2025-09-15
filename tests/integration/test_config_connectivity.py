import os
import threading
import http.server
import socketserver
import time

import pytest


def _start_simple_server(port=0):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')

    httpd = socketserver.TCPServer(('127.0.0.1', port), Handler)

    def serve():
        try:
            httpd.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return httpd


def test_validate_connectivity_success(monkeypatch):
    server = _start_simple_server(0)
    assigned_port = server.server_address[1]

    try:
        monkeypatch.setenv('LETTA_BASE_URL', f'http://127.0.0.1:{assigned_port}')
        monkeypatch.setenv('LETTA_ENVIRONMENT', 'SELF_HOSTED')

        from spds import config

        assert config.validate_letta_config(check_connectivity=True) is True
    finally:
        server.shutdown()
