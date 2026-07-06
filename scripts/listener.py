#!/usr/bin/env python3
import http.server
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "/checkin" in self.path:
            logging.info(
                f"CHECKIN from {self.client_address[0]}: {self.path}"
            )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK\n")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if "/upload" in self.path:
            logging.info(
                f"UPLOAD from {self.client_address[0]}: {length} bytes"
            )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK\n")

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", 8080), Handler)
    logging.info("Listener started on port 8080")
    server.serve_forever()
