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

	# Create a separate connection for publishing messages:
	if pub_conn is None:
		pub_conn = await aioredis.create_redis('redis://localhost')

	# Define a callback that sends messages to this websocket
	async def on_message(channel: bytes, message: bytes):
		await ws.send_text(f"ch: [{channel}] msg: [{message}]\n")

	# Create a subscription for this websocket
	sub = mpx.new_channel_subscription(on_message, 
		lambda e: print(f"Network Error: {type(e)}: {e}"),
		lambda s: print(f"Subscription now active: {s}"))

	# Keep reading from the websocket, use the messages sent by the user
	# to add and remove channels from the subscription.
	# Use +channel to join a channel, -channel to leave.
	# Sending !channel will send the next message to said channel.
	while True:
		msg = None
		try:
			msg = await ws.receive_text()
		except:
			print('ws disconnected')
			sub.close()
			return
		prefix, chan = msg[0], msg[1:]
		if prefix == "+": 
			sub.add(chan)
		elif prefix == "-":
			sub.remove(chan)
		elif prefix == '!':
			# Send the next message to the given channel
			await pub_conn.publish(chan, await ws.receive_text())
		

app = Starlette(debug=True, routes=[
    WebSocketRoute('/ws', endpoint=handle_ws),
])