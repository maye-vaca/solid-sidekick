"""Serve an exported review page over loopback when file:// access is blocked."""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser


HOST = "127.0.0.1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "output"


class ReviewHandler(SimpleHTTPRequestHandler):
    """Serve review files without directory listings or caching."""

    def list_directory(self, path):
        self.send_error(404, "Directory listing disabled")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(output=DEFAULT_OUTPUT, port=0, open_browser=True, timeout=0.0):
    """Bind a loopback server for the review page and return (server, url)."""
    output = Path(output).expanduser().resolve()
    if not output.is_dir():
        raise ValueError(f"Output folder not found: {output}")
    page = output / "review.html"
    if not page.is_file():
        page = output / "viewer.html"
    if not page.is_file():
        raise ValueError(f"No review.html or viewer.html in {output}")

    handler = functools.partial(ReviewHandler, directory=str(output))
    server = ThreadingHTTPServer((HOST, port), handler)
    url = f"http://{HOST}:{server.server_address[1]}/{page.name}"
    print(f"Serving {output} at {url}", flush=True)
    print("Loopback only. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    if timeout > 0:
        threading.Timer(timeout, server.shutdown).start()
    return server, url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=0, help="0 chooses a free loopback port")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser")
    parser.add_argument("--timeout", type=float, default=0.0,
                        help="Stop after N seconds; 0 runs until Ctrl+C")
    args = parser.parse_args()
    try:
        server, _ = serve(args.output, args.port, not args.no_open, args.timeout)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Review server stopped.", flush=True)


if __name__ == "__main__":
    main()
