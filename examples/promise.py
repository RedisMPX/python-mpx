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

	sub = mpx.new_promise_subscription("promise:")

	await ws.send_text(f"# Send a suffix to create a promise.")

	# Keep reading from the websocket, use the messages sent by the user
	# to add and remove channels from the subscription.
	while True:
		suffix = None
		try:
			suffix = await ws.receive_text()
		except:
			print('ws disconnected')
			sub.close()
			return
		
		promise = sub.new_promise(suffix, 5)
		await ws.send_text(f"# Send a pubsub message with redis-cli or any other client to fullfull the promise.")
		await ws.send_text(f"#    > PUBLISH promise:{suffix} 'your-promise-payload'")
		await ws.send_text(f"# The promise will expire in 5 seconds.")
		try:
			await ws.send_text(await promise)
		except asyncio.TimeoutError:
			print("the promise timed out")

app = Starlette(debug=True, routes=[
    WebSocketRoute('/ws', endpoint=handle_ws),
])