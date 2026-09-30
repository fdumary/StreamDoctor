from starlette.responses import JSONResponse


class RequestBodyLimit:
    """Bound request bytes before multipart parsing, including chunked requests."""

    def __init__(self, app, photo_limit: int):
        self.app = app
        self.photo_limit = photo_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT"}:
            return await self.app(scope, receive, send)
        is_upload = scope["method"] == "POST" and scope["path"].rstrip("/").endswith("/photos")
        limit = self.photo_limit if is_upload else 64 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(
                scope, receive, send
            )
        if length > limit:
            return await JSONResponse({"detail": "Request body exceeds the size limit"}, status_code=413)(
                scope, receive, send
            )
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            size += len(data)
            if size > limit:
                return await JSONResponse({"detail": "Request body exceeds the size limit"}, status_code=413)(
                    scope, receive, send
                )
            chunks.append(data)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def limited_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, limited_receive, send)
