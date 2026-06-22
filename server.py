#!/usr/bin/env python3
"""Local dev server for the Docker Image Pusher management page.

Serves index.html, handles POST /save to write images.txt,
and auto-commits via git.
"""

import http.server
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGES_FILE = ROOT / "images.txt"
PORT = 8765


def run_git(*args: str) -> tuple[int, str]:
    """Run a git command in ROOT, return (returncode, output)."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip() + result.stderr.strip()
    except Exception as e:
        return -1, str(e)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self) -> None:
        if self.path == "/save":
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                content = data.get("content", "")
                # 1. Write images.txt
                IMAGES_FILE.write_text(content)
                print(f"[OK] Saved images.txt ({len(content)} bytes)")

                # 2. git add
                rc, out = run_git("add", "images.txt")
                if rc != 0:
                    raise RuntimeError(f"git add failed: {out}")

                # 3. git commit
                rc, out = run_git("commit", "-m", "Update images.txt")
                if rc != 0:
                    if "nothing to commit" in out:
                        print("[OK] No changes to commit")
                        msg = "文件未变化，无需提交"
                    else:
                        raise RuntimeError(f"git commit failed: {out}")
                else:
                    print(f"[OK] git commit: {out}")
                    msg = "已提交"

                # 4. git push
                rc, out = run_git("push")
                if rc != 0:
                    raise RuntimeError(f"git push failed: {out}")
                msg += " & 已推送"

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "message": msg}).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                print(f"[ERROR] {e}")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


def main() -> None:
    os.chdir(str(ROOT))

    # Verify we're in a git repo
    rc, _ = run_git("status")
    if rc != 0:
        print("WARNING: Not a git repository, save will still work but won't commit.")

    server = http.server.ThreadingHTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Docker Image Pusher -> {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
        server.shutdown()


if __name__ == "__main__":
    main()
