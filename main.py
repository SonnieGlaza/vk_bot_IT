"""HTTP healthcheck + VK бот (Long Poll) в фоне."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os

from bot_vk import start_bot_thread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        logging.getLogger("http").info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK\n")


def main() -> None:
    t = start_bot_thread()
    if t is None:
        logging.getLogger(__name__).error(
            "VK-бот не запущен: проверьте переменные VK_GROUP_TOKEN и VK_GROUP_ID "
            "на хостинге. HTTP продолжает работать для проверки деплоя."
        )

    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    logging.getLogger(__name__).info("HTTP listening on port %s", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
