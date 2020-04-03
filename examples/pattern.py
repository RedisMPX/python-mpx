import asyncio
import aioredis
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from redismpx import Multiplexer

# Pass to Multiplexer the same connection options that
# aioredis.create_redis() would accept.
mpx = Multiplexer('redis://localhost')

pub_conn = None

async def handle_ws(ws):
    global pub_conn
    await ws.accept()

    # Define a callback that sends messages to this websocket
    async def on_message(channel: bytes, message: bytes):
        await ws.send_text(f"ch: [{channel.decode()}] msg: [{message.decode()}]\n")

    # Create a subscription for this websocket
    sub = mpx.new_pattern_subscription("pattern:*",
        on_message, 
        lambda e: print(f"Network Error: {type(e)}: {e}"),
        lambda s: print(f"Subscription now active: {s}"))

    await ws.send_text('# Send messages with redis-cli to any channel matching `pattern:*` to received them.')
    await ws.send_text('# e.g.  > PUBLISH pattern:banana "Hello world!"')

    while True:
        await ws.receive_text()
        

app = Starlette(debug=True, routes=[
    WebSocketRoute('/ws', endpoint=handle_ws),
])