import asyncio
import logging
import aioredis
from typing import Union, Awaitable, Callable, Optional
from .connection import Conn
from .utils import Box, as_bytes, jitter_exp_backoff
from .channel_subscription import ChannelSubscription
from .pattern_subscription import PatternSubscription
from .promise_subscription import PromiseSubscription


OnMessage = Union[Callable[[bytes, bytes], None], Callable[[bytes, bytes], Awaitable[None]]]
OnDisconnect = Union[Callable[[Exception], None], Callable[[Exception], Awaitable[None]]]
OnActivation = Union[Callable[[bytes], None],Callable[[bytes], Awaitable[None]]]

class Multiplexer:
	"""
	A Multiplexer instance corresponds to one Redis Pub/Sub connection 
	that will be shared by multiple subscription instances. 

	Multiplexer accepts the same connection options 
	that you can specify with :func:`aioredis.create_connection`.

	See the documentation of `aio-libs/aioredis` for more information.

	Usage example:

	.. highlight:: python

    .. code-block:: python
	
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

	"""

	def __init__(self, *args, **kwargs):
		kwargs["connection_cls"] = Conn
		self.channels = {}
		self.patterns = {}
		self.active_channels = set()
		self.active_patterns = set()
		self.subscriptions = []
		self.connection = None
		self.connection_options = (args, kwargs)
		self.must_exit = False
		self.reconnecting = True
		self.conn_reader = asyncio.create_task(self._read_messages())


	async def _reconnect(self, cause):
		if self.reconnecting:
			return
		logging.info(f"redismpx id({id(self)}): reconnecting because of error: {cause}")
		for s in self.subscriptions:
			if s.on_disconnect is not None:
				try:
					if asyncio.iscoroutinefunction(s.on_disconnect):
						await s.on_disconnect(cause)
					else:
						s.on_disconnect(cause)
				except Exception as e:
					logging.warning(f"redismpx id({id(self)}): on_disconnect function threw exception: {e}")

		self.reconnecting = True
		self.active_channels = set()
		self.active_patterns = set()
		self.conn_reader.cancel()
		try:
			await self.conn_reader
		except:
			pass
		self.connection.close()
		self.connection = None
		self.conn_reader = asyncio.create_task(self._read_messages())

	async def _read_messages(self):
		args, kwargs = self.connection_options
		# Keep trying to connect
		tries = 1
		while not self.must_exit:
			try:	
				self.connection = await aioredis.create_connection(*args, **kwargs)
				break # DO NOT DELETE THIS LINE LMAO
			except Exception as e:
				# Exp backoff + jitter
				sleep_ms = jitter_exp_backoff(8, 512, tries)
				await asyncio.sleep(sleep_ms/1000)
				tries += 1

		self.reconnecting = False

		# Resubscribe to all channels, if any is present.
		if len(self.channels) > 0:
			self.connection.write_command(b"SUBSCRIBE", *self.channels.keys())

		try:
			async for msg in self.connection.read_message():
				print(msg)

				if msg[0] == b"message":
					ch_name = msg[1]
					if ch_name in self.channels:
						for fn_box in self.channels[ch_name]:
							try:
								if asyncio.iscoroutinefunction(fn_box.on_message):
									await fn_box.on_message(ch_name, msg[2])
								else:
									fn_box.on_message(ch_name, msg[2])
							except Exception as e:
								logging.warning(f"redismpx id({id(self)}): on_message function threw exception: {e}")
					continue

				if msg[0] == b"pmessage":
					pat_name = msg[1]
					if pat_name in self.patterns:
						for fn_box in self.patterns[pat_name]:
							try:
								if asyncio.iscoroutinefunction(fn_box.on_message):
									await fn_box.on_message(msg[2], msg[3])
								else:
									fn_box.on_message(msg[2], msg[3])
							except Exception as e:
								logging.warning(f"redismpx id({id(self)}): on_message function threw exception: {e}")
					continue

				# SUBSCRIPTIONS 

				if msg[0] == b'unsubscribe':
					ch_name = msg[1]
					self.active_channels.remove(ch_name)
					continue

				if msg[0] == b'punsubscribe':
					pat_name = msg[1]
					self.active_patterns.remove(pat_name)
					continue

				if msg[0] == b'subscribe':
					ch_name = msg[1]
					self.active_channels.add(ch_name)
					if ch_name in self.channels:
						for fn_box in self.channels[ch_name]:
							if fn_box.on_activation is None:
								continue

							try:
								if asyncio.iscoroutinefunction(fn_box.on_activation):
									await fn_box.on_activation(ch_name)
								else:
									fn_box.on_activation(ch_name)
							except Exception as e:
								logging.warning(f"redismpx id({id(self)}): on_activation function threw exception: {e}")
					continue

				if msg[0] == b'psubscribe':
					pat_name = msg[1]
					self.active_channels.add(pat_name)

					if pat_name in self.patterns:
						for fn_box in self.patterns[pat_name]:
							if fn_box.on_activation is None:
								continue

							try:
								if asyncio.iscoroutinefunction(fn_box.on_activation):
									await fn_box.on_activation(pat_name)
								else:
									fn_box.on_activation(pat_name)
							except Exception as e:
								logging.warning(f"redismpx id({id(self)}): on_activation function threw exception: {e}")
					continue


		except Exception as e:
			asyncio.create_task(self._reconnect(e))
	
	def new_channel_subscription(self, 
		on_message: OnMessage, 
		on_disconnect: Optional[OnDisconnect], 
		on_activation: Optional[OnActivation]) -> ChannelSubscription:
		"""
		Creates a new ChannelSubscription tied to the Multiplexer. 

		Before disposing of a ChannelSubscription you must call its 
		:func:`~redismpx.ChannelSubscription.close` method.

		The arguments `on_disconnect` and `on_activation` can be `None` 
		if you're not interested in the corresponding types of event. 

		:param on_message: a (async or non) function that gets called for every message recevied.
		:param on_disconnect: a (async or non) function that gets called when the connection is lost.
		:param on_activation: a (async or non) function that gets called when a subscription goes into effect.
		
		"""
		if on_message is None:
			raise Exception("on_message cannot be None")
		sub = ChannelSubscription(self, on_message, on_disconnect, on_activation)
		self.subscriptions.append(sub)
		return sub

	def new_pattern_subscription(self, 
		pattern: Union[str, bytes], 
		on_message: OnMessage, 
		on_disconnect: Optional[OnDisconnect], 
		on_activation: Optional[OnActivation]) -> PatternSubscription:
		"""
		Creates a new PatternSubscription tied to the Multiplexer. 

		Before disposing of a PatternSubscription you must call its 
		:func:`~redismpx.PatternSubscription.close` method.

		The arguments `on_disconnect` and `on_activation` can be `None` 
		if you're not interested in the corresponding types of event. 
	
		:param pattern: the Redis Pub/Sub pattern to subscribe to.
		:param on_message: a (async or non) function that gets called for every message recevied.
		:param on_disconnect: a (async or non) function that gets called when the connection is lost.
		:param on_activation: a (async or non) function that gets called when a subscription goes into effect.
		
		"""
		if on_message is None:
			raise Exception("on_message cannot be None")
		sub = PatternSubscription(self, pattern, on_message, on_disconnect, on_activation)
		self.subscriptions.append(sub)
		return sub

	def new_promise_subscription(self, prefix: Union[str, bytes]) -> PromiseSubscription:
		""" 
		Creates a new PromiseSubscription tied to the Multiplexer. 

		Before disposing of a PromiseSubscription you must call its 
		:func:`~redismpx.PromiseSubscription.close` method.

		The prefix argument is used to create internally a PatternSubscription 
		that will match all channels that start with the provided prefix. 

		A Promise represents a timed, uninterrupted, single-message 
		subscription to a Redis Pub/Sub channel. If network 
		connectivity gets lost, thus causing an interruption, 
		the Promise will be failed (unless already fullfilled). 
		Use NewPromise from PromiseSubscription to create a new Promise. 

		:param prefix: the prefix under which all Promises will be created under.
		"""
		return PromiseSubscription(self, prefix)

	def close(self):
		self.must_exit = True
		self.conn_reader.cancel()
		self.connection.close()

	async def _log_exeptions(self, callback, *args, **kwargs):
		try:
			if asyncio.iscoroutinefunction(callback):
				await callback(*args, **kwargs)
			else:
				callback(*args, **kwargs)
		except Exception as e:
			logging.warning(f"redismpx id({id(self)}): on_disconnect function threw exception: {e}")

	def _remove_subscription(self, sub):
		self.subscriptions.remove(sub)

	def _add(self, channel, fn_box):
		if self.must_exit:
			raise Exception("tried to use a closed multiplexer")

		# Are we already subscribed inside the multiplexer?
		if channel not in self.channels:
			try:
				if self.connection is not None:
					self.connection.write_command(b"SUBSCRIBE", channel)
			except Exception as e:
				asyncio.create_task(self._reconnect(e))
			self.channels[channel] = []
		else:
			# We are already subscribed, check if the sub is active
			# if so, we immediately trigger on_activation
			if channel in self.active_channels:
				if fn_box.on_activation is not None:
					asyncio.create_task(self._log_exeptions(fn_box.on_activation, channel))
		self.channels[channel].append(fn_box)

	def _remove(self, channel, fn_box):
		if self.must_exit:
			raise Exception("tried to use a closed multiplexer")

		fn_box_list = self.channels[channel]
		fn_box_list.remove(fn_box)
		if len(fn_box_list) == 0:
			del self.channels[channel]
			try:
				if self.connection is not None:
					self.connection.write_command(b"UNSUBSCRIBE", channel)
			except Exception as e:
				asyncio.create_task(self._reconnect(e))


	def _add_pattern(self, pattern, fn_box):
		if self.must_exit:
			raise Exception("tried to use a closed multiplexer")

		# Are we already subscribed inside the multiplexer?
		if pattern not in self.patterns:
			try:
				if self.connection is not None:
					self.connection.write_command(b"PSUBSCRIBE", pattern)
			except Exception as e:
				asyncio.create_task(self._reconnect(e))
			self.patterns[pattern] = []
		else:
			# We are already subscribed, check if the sub is active
			# if so, we immediately trigger on_activation
			if pattern in self.active_patterns:
				if fn_box.on_activation is not None:
					asyncio.create_task(self._log_exeptions(fn_box.on_activation, pattern))
		self.patterns[pattern].append(fn_box)

	def _remove_pattern(self, pattern, fn_box):
		if self.must_exit:
			raise Exception("tried to use a closed multiplexer")

		fn_box_list = self.patterns[pattern]
		fn_box_list.remove(fn_box)
		if len(fn_box_list) == 0:
			del self.patterns[pattern]
			try:
				if self.connection is not None:
					self.connection.write_command(b"PUNSUBSCRIBE", pattern)
			except Exception as e:
				asyncio.create_task(self._reconnect(e))
