import asyncio

import websockets


async def test():
    async with websockets.connect("wss://echo.websocket.events", additional_headers=[("X-Test", "value")]) as ws:
        await ws.send("hello")
        print(await ws.recv())


asyncio.run(test())
