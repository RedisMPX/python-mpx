import asyncio
import aioredis
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from redismpx import Multiplexer

# Pass to Multiplexer the same connection options that
# aioredis.create_redis() would accept.
mpx = Multiplexer('redis://localhost')

async def handle_ws(ws):
	await ws.accept()

	sub = mpx.new_promise_subscription("test")

	# Keep reading from the websocket, use the messages sent by the user
	# to add and remove channels from the subscription.
	while True:
		msg = None
		try:
			msg = await ws.receive_text()
		except:
			print('ws disconnected')
			sub.close()
			return
		prefix, msg = msg[0], msg[1:]
		if prefix == "+":
			promise = sub.new_promise(msg, 10)
			print(await promise)
		

app = Starlette(debug=True, routes=[
    WebSocketRoute('/ws', endpoint=handle_ws),
])