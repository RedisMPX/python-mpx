.. RedisMPX documentation master file, created by
   sphinx-quickstart on Thu Mar 26 21:11:02 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to RedisMPX's documentation!
====================================

Abstract
--------

When bridging multiple application instances through Redis Pub/Sub it's easy to end up needing
support for multiplexing. RedisMPX streamlines this process in a consistent way across multiple
languages by offering a consistent set of features that cover the most common use cases.

The library works under the assumption that you are going to create separate subscriptions
for each client connected to your service (e.g. WebSockets clients):

- ChannelSubscription allows you to add and remove individual Redis
  PubSub channels similarly to how a multi-room chat application would need to.
- PatternSubscription allows you to subscribe to a single Redis Pub/Sub pattern.
- PromiseSubscription allows you to create a networked promise system.


Installation
------------

Requires Python 3.7+, based on `aio-libs/aioredis <https://github.com/aio-libs/aioredis>`_,
an AsyncIO Redis client.

`pip install redismpx`

Features
--------
- Simple channel subscriptions
- Pattern subscriptions
- `Networked promise system <https://python-mpx.readthedocs.io/en/latest/#redismpx.Multiplexer.new_promise_subscription>`_
- Automatic reconnection with exponetial backoff + jitter


Classes
-------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. automodule:: redismpx
   :members:



