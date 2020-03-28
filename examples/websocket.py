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

	# Define a callback that sends messages to this websocket
	async def on_message(channel, message):
		await ws.send_text(f"ch: [{channel}] msg: [{message}]\n")
		raise Exception("blargh!")

	# Create a subscription for this websocket
	sub = mpx.new_pattern_subscription("test*", on_message, lambda x: print(f"YEPPPPP!! {type(x)}"), None)

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
			sub.add(msg)
		elif prefix == "-":
			sub.remove(msg)
		

app = Starlette(debug=True, routes=[
    WebSocketRoute('/ws', endpoint=handle_ws),
])