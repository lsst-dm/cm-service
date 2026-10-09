from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import config


class RootPathMiddleware:
    """ASGI Middleware to manipulate the stripped root_path prefix when client
    is using an ingress or reverse proxy.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Set the root-path in scope if forwarded prefix is available in
        request headers.
        """
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))

            if b"x-forwarded-prefix" in headers:
                scope["root_path"] = config.asgi.root_path

        await self.app(scope, receive, send)
