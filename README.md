# RedisMPX
RedisMPX is a Redis Pub/Sub multiplexer library written in multiple languages and [live coded on Twitch](https://twitch.tv/kristoff_it).

## Abstract
When bridging multiple application instances through Redis Pub/Sub it's easy to end up needing
support for multiplexing. RedisMPX streamlines this process in a consistent way across multiple
languages by offering a consistent set of features that cover the most common use cases.

The library works under the assumption that you are going to create separate subscriptions
for each client connected to your service (e.g. WebSockets clients):

- ChannelSubscription allows you to add and remove individual Redis
  PubSub channels similarly to how a multi-room chat application would need to.
- PatternSubscription allows you to subscribe to a single Redis Pub/Sub pattern.
- PromiseSubscription allows you to create a networked promise system.


## Installation
Requires Python 3.7+, based on [aio-libs/aioredis](https://github.com/aio-libs/aioredis),
an AsyncIO Redis client.

`pip install redismpx`

## Features
- Simple channel subscriptions
- Pattern subscriptions
- **[Networked promise system](https://python-mpx.readthedocs.io/en/latest/#redismpx.Multiplexer.new_promise_subscription)**
- Automatic reconnection with exponetial backoff + jitter

## Documentation
- [API Reference](https://python-mpx.readthedocs.io/en/latest/)
- [Examples](/examples/)

## Usage
```python
from redismpx import Multiplexer

# Pass to Multiplexer the same connection options that
# aioredis.create_connection() would accept.
mpx = Multiplexer('redis://localhost') 

# on_message is a callback (can be async)
# that accepts a channel name and a message.
async def my_on_message(channel: bytes, message: bytes):
    await websocket.send(f"ch: {channel} msg: {message}")

# on_disconnect is a callback (can be async) 
# that accepts the error that caused the disconnection.
def my_on_disconnect(error: Exception):
    print("oh no!")

# on_activation is a callback (can be async)
# that accepts the name of the channel or pattern
# whose subscription just became active (depends
# on whether it's attached to a ChannelSubscription
# or a PatternSubscription).
def my_on_activation(name: bytes):
    print("activated:", name)

# you can also pass None in place of `on_disconnect`
# and `on_activation` if you're not interested in 
# reacting to those events.

# Use `mpx` to create new subscriptions.
channel_sub = mpx.new_channel_subcription(
    my_on_message, my_on_disconnect, None) 
pattern_sub = mpx.new_pattern_subscription("hello-*", 
    my_on_message, None, my_on_activation)
promise_sub = mpx.new_promise_subscription("hello-")
```

### ChannelSubscription
```python
# Create the ChannelSubscription.
channel_sub = mpx.new_channel_subcription(
    lambda ch, msg: print(f"Message @ {ch}: {msg}"),
    lambda e: print(f"Network Error: {type(e)}: {e}"),
    lambda s: print(f"Subscription now active: {s}")) 

# Add channels
channel_sub.add("chan1")
channel_sub.add("chan2")
channel_sub.add("chan3")

# Remove a channel
channel_sub.remove("chan2")

# Close the subscription
channel_sub.close()
```

### PatternSubscription
```python
# Create the PatternSubscription.
# Note how it also requires the pattern.
pattern_sub = mpx.new_pattern_subcription(
    "notifications:*",
    lambda ch, msg: print(f"Message @ {ch}: {msg}"),
    lambda e: print(f"Network Error: {type(e)}: {e}"),
    lambda s: print(f"Subscription now active: {s}")) 

# PatternSubscriptions can only be closed
pattern_sub.close()
```

### PromiseSubscription
```python
# Create the subscription. 
# Note how it doesn't accept any callback.
promise_sub = mpx.new_promise_subscription("hello-")

# When first created (and after a network error that causes 
# a reconnection), a PromiseSubscription is not immediately 
# able to create new promises as it first needs the underlying
# PatternSubscription to become active. This async function
# waits for that event.
await promise_sub.wait_for_activation()


# Create a new promise. It might fail if the subscription is 
# not active.
try:
    promise = promise_sub.new_promise("world", 10)
    # The provided suffix will be composed with the subscription's
    # prefix to create the final Redis Pub/Sub channel from which
    # the message is expected to come. In this example, to fullfill
    # the promise you could send, using redis-cli (or any other client):
    #
    #   > PUBLISH hello-world "your-promise-payload"
    #
except redismpx.InactiveSubscription:
    # Wait and then Retry? Return an error to the user? Up to you.

# A way of creating a promise that ensures no InactiveSubscription error 
# will trigger. Note that this method needs to be awaited.
# The timer will start only after the promise has been created.
promise = await promise_sub.wait_for_new_promise("world", 10)

# A Promise represents a timed, uninterrupted, single-message 
# subscription to a Redis Pub/Sub channel. If network 
# connectivity gets lost, thus causing an interruption, 
# the Promise will be failed (unless already fullfilled). 

# Resolve the promise
try:
    result = await promise
    print(result) # prints b'your-promise-payload'
except asyncio.TimeoutError:
    # The promise timed out.
except asyncio.CancelledError:
    # The promise was canceled. This happens when
    # a reconnection event triggers while the promise
    # is not yet resolved. 

# Close the subscription (will automatically cancel all
# outstanding promises and unlock all `wait_for_*` waiters).
promise_sub.close()
```

## WebSocket Example
This is a more realistic example of how to use RedisMPX.

### Code
This code is also available in [examples/channel.py](/examples/channel.py).

```python
# channel.py

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
        await ws.send_text(f"ch: [{channel.decode()}] msg: [{message.decode()}]\n")

    # Create a subscription for this websocket
    sub = mpx.new_channel_subscription(on_message, 
        lambda e: print(f"Network Error: {type(e)}: {e}"),
        lambda s: print(f"Subscription now active: {s}"))

    # Keep reading from the websocket, use the messages sent by the user
    # to add and remove channels from the subscription.
    # Use +channel to join a channel, -channel to leave.
    # Sending !channel will send the next message to said channel.
    await ws.send_text('# Use +channel to join a channel, -channel to leave.')
    await ws.send_text('# Sending !channel will send the next message to said channel.')
    await ws.send_text('# To see a message sent to a given channel, you must have joined it beforehand.')

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
```

### Dependences
`pip install redismpx aioredis starlette uvcorn`

### Launching the example
`$ uvicorn websocket:app`

### Interacting with the example
The application works like a simple WebSocket chat application that 
expects commands from the user.

- Sending `+hello` will subscribe you to channel `hello`, while `-hello` will do the opposite.
- Sending `!hello` will broadcast the next message you send to `hello`.
- You can use whatever channel name you like.

To send those commands you can use a browser:
```js
// To create a websocket connection to localhost
// you will need to deal with the browser's security
// policies. Opening a file on the local filesystem
// and typing these commands in the console should
// do the trick.
let ws = new WebSocket("ws://localhost:8000/ws")
ws.onmessage = (x) => console.log("message:", x.data)
ws.send("+test")
ws.send("!test")
ws.send("hello world!")
```
A more handy way of interacting with websockets are command-line clients:
- https://github.com/hashrocket/ws (recommended)
- https://github.com/esphen/wsta

