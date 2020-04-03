import asyncio
from typing import Union, Awaitable
from .utils import as_bytes, SubscriptionIsClosed
from .internal import List, ListNode

class InactiveSubscription(Exception):
	pass

class PromiseSubscription:
	"""
	A PromiseSubscription allows you to wait for individual Redis 
	Pub/Sub messages with support for timeouts. This effectively 
	creates a networked promise system. 

	It makes use of a PatternSubscription internally to make creating 
	new promises as lightweight as possible (no subscribe/unsubscribe 
	command is sent to Redis to fullfill or expire a Promise). 
	Consider always calling :func:`~redismpx.PromiseSubscription.wait_for_activation` after creating a new PromiseSubscription. 

	Use :func:`~redismpx.Multiplexer.new_promise_subscription` to create a new PromiseSubscription.
	
	Usage example:

	.. highlight:: python

    .. code-block:: python
	
		# This subscription will allow you to produce promises
		# under the `hello-` prefix.
		promise_sub = mpx.new_promise_subscription("hello-")

		# Wait for the subscription to become active.
		await promise_sub.wait_for_activation()

		# Create a promise with a timeout of 10s.
		p = promise_sub.new_promise("world", 10)

		# Publish a message in Redis Pub/Sub using redis-cli
		# > PUBLISH hello-world "success!"

		# Obtain the result.
		print(await p)

		# prints "success!"

	"""

	def __init__(self, multiplexer, prefix):
		self.channels = {}
		self.multiplexer = multiplexer
		self.prefix = as_bytes(prefix)
		self.active = asyncio.Event()
		self.closed = False
		self.pat_sub = multiplexer.new_pattern_subscription(
			self.prefix + b'*', self.on_message, self.on_disconnect, self.on_activation)

	def new_promise(self, suffix: Union[str, bytes], timeout: Union[int, float, None]) -> Awaitable[bytes]:
		"""
		Creates a new Promise for the given suffix. 
		The suffix gets composed with the prefix specified when creating 
		the PromiseSubscription to create the final Redis Pub/Sub channel name. 
		The underlying PatternSubscription will receive all messages sent under 
		the given prefix, thus ensuring that new promises get into effect as soon 
		as this method returns. Trying to create a new Promise while the 
		PromiseSubscription is not active will cause this method to throw 
		:class:`~redismpx.InactiveSubscription`. 

		A promise that expires will throw a `asyncio.TimeoutError`.


		:param suffix: the suffix that will be appended to the subscription's prefix
		:param timeout: a timeout for the promise expressed in seconds
		:return: The message received from Pub/Sub.
		"""
		if self.closed:
			raise Exception("tried to use a closed PromiseSubscription")
		if not self.active.is_set():
			raise InactiveSubscription("the subscription is inactive")

		suffix = as_bytes(suffix)
		channel = self.prefix + suffix

		if channel not in self.channels:
			self.channels[channel] = List(None)

		loop = asyncio.get_running_loop()
		fut = loop.create_future()
		fut.channel = channel
		node = ListNode(fut=fut)
		fut.node = node
		fut.add_done_callback(self._cleanup)
		self.channels[channel].prepend(node)

		return asyncio.wait_for(fut, timeout)

	async def wait_for_activation(self) -> Awaitable[None]:
		"""
		Blocks until the subscription becomes active. 

		Closing the subscription will cause this method to throw 
		:class:`~redismpx.SubscriptionIsClosed`.
		"""
		await self.active.wait()
		if self.closed:
			raise SubscriptionIsClosed("tried to use a closed PromiseSubscription")

	async def wait_for_new_promise(self, prefix: Union[str, bytes]) -> Awaitable[bytes]:
		"""
		Like :func:`~redismpx.PromiseSubscription.new_promise` but waits for
		the subscription to become active instead of throwing 
		:class:`~redismpx.InactiveSubscription`.

		Closing the subscription will cause this method to throw 
		:class:`~redismpx.SubscriptionIsClosed`.
		"""
		while True:
			await self.active.wait()
			if self.closed:
				raise SubscriptionIsClosed("tried to use a closed PromiseSubscription")
			try:
				return self.new_promise(prefix)
			except:
				pass

	def clear(self) -> None:
		"""Cancels all outstanding promises"""

		if self.closed:
			raise SubscriptionIsClosed("tried to use a closed PromiseSubscription")

		for ch in self.channels:
			for node in self.channels[ch]:
				node.fut.cancel()
			del self.channels[ch]

	def close(self) -> None:
		"""Closes the subscription and cancels all outstanding promises."""

		if self.closed:
			raise SubscriptionIsClosed("tried to use a closed PromiseSubscription")

		self.clear()
		self.closed = True
		self.active.set()
		self.pat_sub.close()
		

	def on_disconnect(self, error):
		if not self.closed:
			self.active.clear()
			for ch in self.channels:
				for node in self.channels[ch]:
					node.fut.cancel()
				del self.channels[ch]

	def on_activation(self, pattern):
		self.active.set()

	async def on_message(self, channel, message):
		if channel in self.channels:
			for node in self.channels[channel]:
				node.fut.set_result(message)
			del self.channels[channel]

	def _cleanup(self, fut):
		try:
			fut.exception() 
		except:
			print(self.channels[fut.channel]._head is fut.node)
			if fut.node.remove_from_list().is_empty():
				del self.channels[fut.channel]
