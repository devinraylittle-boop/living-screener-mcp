from __future__ import annotations

from starlette.responses import JSONResponse

from app.config import Settings


class BearerAuthMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope.get("type") != "http" or path in {"/health", "/config", "/version", "/tools"}:
            await self.app(scope, receive, send)
            return
        if not self.settings.hosted_mode:
            await self.app(scope, receive, send)
            return
        expected = f"Bearer {self.settings.screener_auth_token}"
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
        if headers.get("authorization") != expected:
            response = JSONResponse({"error": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
