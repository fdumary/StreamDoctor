import asyncio

from app.core.body_limit import RequestBodyLimit


def test_chunked_body_limit_without_content_length():
    async def run():
        called = False

        async def app(scope, receive, send):
            nonlocal called
            called = True

        middleware = RequestBodyLimit(app, photo_limit=8)
        chunks = iter(
            [
                {"type": "http.request", "body": b"12345", "more_body": True},
                {"type": "http.request", "body": b"67890", "more_body": False},
            ]
        )
        messages = []

        async def receive():
            return next(chunks)

        async def send(message):
            messages.append(message)

        await middleware(
            {"type": "http", "method": "POST", "path": "/api/v1/reports/1/photos", "headers": []},
            receive,
            send,
        )
        assert not called
        assert messages[0]["status"] == 413

    asyncio.run(run())
