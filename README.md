# python-mpx
RedisMPX is a Redis Pub/Sub multiplexer written in multiple languages and livecoded on Twitch.

## Abstract
RedisMPX implementation for Python.

- [Twitch channel](https://twitch.tv/kristoff_it)
- [YouTube VOD archive](https://www.youtube.com/user/Kappaloris/videos)

## Status
Main functionality completed. Needs testing.

## Features
- Simple channel subscriptions
- Pattern subscriptions
- **[Networked promise system](https://python-mpx.readthedocs.io/en/latest/#redismpx.Multiplexer.new_promise_subscription)**
- Connection retry with exponetial backoff + jitter

## Documentation
- [API Reference](https://python-mpx.readthedocs.io/en/latest/)
- [Examples](/examples/)

## Quickstart
```python
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
	sub = mpx.new_channel_subscription(on_message, lambda x: print(f"Error: {type(x)}"), None)

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
```
