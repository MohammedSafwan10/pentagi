#!/usr/bin/env python3
"""Streaming OpenCode Go gateway; never logs credentials or prompts."""
import http.server
import json
import os
import socketserver
import urllib.error
import urllib.request
from opencode_responses import chat_chunks, to_chat, to_responses

PORT = int(os.environ.get('PORT', '8080'))
OPENCODE_BASE = 'https://opencode.ai'
TIMEOUT = float(os.environ.get('OPENCODE_TIMEOUT', '180'))
MAX_BODY = 16 * 1024 * 1024
ROUTES = {'/zen/go/v1/models', '/zen/go/v1/chat/completions', '/zen/go/v1/responses'}

class OpenCodeProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(TIMEOUT)

    def _send_data(self, status, content_type, data):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def _error(self, status, message):
        self._send_data(status, 'application/json', json.dumps({'error': {'message': message}}).encode())

    def _filter_headers(self):
        headers = {'User-Agent': 'pentagi-opencode/1.0',
                   'x-opencode-session': self.headers.get('x-opencode-session') or 'pentagi-session',
                   'Content-Type': 'application/json'}
        if self.headers.get('Authorization'):
            headers['Authorization'] = self.headers['Authorization']
        return headers

    def do_GET(self):
        if self.path == '/healthz':
            return self._send_data(200, 'application/json', b'{"status":"ok"}')
        if self.path != '/zen/go/v1/models':
            return self._error(404, 'Unknown gateway route')
        self._forward(None)

    def do_POST(self):
        if self.path not in ROUTES - {'/zen/go/v1/models'}:
            return self._error(404, 'Unknown gateway route')
        if self.headers.get('Transfer-Encoding'):
            return self._error(400, 'Content-Length is required')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self._error(400, 'Invalid Content-Length')
        if not 0 < length <= MAX_BODY:
            return self._error(413 if length > MAX_BODY else 400, 'Invalid request size')
        try:
            body = self.rfile.read(length)
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get('model'), str):
                return self._error(400, 'A JSON object with a model is required')
        except (ValueError, UnicodeError):
            return self._error(400, 'Invalid JSON')
        if self.path.endswith('/chat/completions') and payload['model'].startswith('muse-spark'):
            return self._muse(payload)
        print(f"[PROXY POST] model={payload['model']} stream={bool(payload.get('stream'))}", flush=True)
        self._forward(body)

    def _muse(self, payload):
        started = False
        try:
            body = json.dumps(to_responses(payload)).encode()
        except (ValueError, KeyError, TypeError) as error:
            return self._error(400, str(error))
        request = urllib.request.Request(OPENCODE_BASE + '/zen/go/v1/responses',
                                         data=body, headers=self._filter_headers())
        print(f"[MUSE] model={payload['model']} stream={bool(payload.get('stream'))}", flush=True)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                if not payload.get('stream'):
                    data = to_chat(json.load(response), payload['model'])
                    return self._send_data(200, 'application/json', json.dumps(data).encode())
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                started = True
                for chunk in chat_chunks(response, payload['model']):
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                    self.wfile.flush()
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
        except urllib.error.HTTPError as error:
            self._send_data(error.code, error.headers.get('Content-Type', 'application/json'), error.read())
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except (OSError, ValueError, KeyError, TypeError) as error:
            if started:
                self.wfile.write(('data: ' + json.dumps({'error': {'message': str(error)}}) + '\n\n').encode())
                self.wfile.flush()
            else:
                self._error(502, 'Muse upstream response failed: ' + str(error))

    def _forward(self, body):
        request = urllib.request.Request(OPENCODE_BASE + self.path, data=body, headers=self._filter_headers())
        started = False
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                content_type = response.headers.get('Content-Type', 'application/json')
                if 'text/event-stream' not in content_type:
                    return self._send_data(response.status, content_type, response.read())
                self.send_response(response.status)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                started = True
                while chunk := response.read1(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as error:
            self._send_data(error.code, error.headers.get('Content-Type', 'application/json'), error.read())
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except (OSError, urllib.error.URLError):
            if started:
                self.close_connection = True
            else:
                self._error(502, 'OpenCode upstream connection failed or timed out')

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == '__main__':
    server = ThreadedHTTPServer(('0.0.0.0', PORT), OpenCodeProxyHandler)
    print(f'OpenCode gateway listening on port {PORT}', flush=True)
    server.serve_forever()
