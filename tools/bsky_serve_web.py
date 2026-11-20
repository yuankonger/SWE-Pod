"""Serves an Expo web export (social-app's `dist/`) as the app's own web server would: a file that exists is served,
any other path gets `index.html`, so the app's router decides what it shows.

    python3 bsky_serve_web.py <dist dir> <port>

Standard library only.
"""
import functools
import http.server
import os
import sys


class AppHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or (os.path.isdir(path) and not os.path.isfile(os.path.join(path, "index.html"))):
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    root, port = sys.argv[1], int(sys.argv[2])
    handler = functools.partial(AppHandler, directory=root)
    http.server.ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
