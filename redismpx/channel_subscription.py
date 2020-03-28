from typing import Union
from .utils import Box, as_bytes


class ChannelSubscription:
	"""
	A ChannelSubscription ties a on_message callback to zero or more Redis Pub/Sub channels.
	Use :func:`~redismpx.Multiplexer.new_channel_subscription` to create a new 
	ChannelSubscription.


	Usage example:

	.. highlight:: python

    .. code-block:: python
		
		# When created, a ChannelSubscription is empty.
		channel_sub = mpx.new_channel_subcription(
			my_on_message, my_on_disconnect, None)

		# You can then add more channels to the subscription.
		channel_sub.add("hello-world")
		channel_sub.add("banana")

		# and remove them
		channel_sub.remove("banana")
	"""

	def __init__(self, multiplexer, on_message, on_disconnect, on_activation):
		self.channels = {}
		self.mpx = multiplexer
		self.on_message = on_message
		self.on_disconnect = on_disconnect
		self.on_activation = on_activation
		self.closed = False

	def add(self, channel: Union[str, bytes]) -> None:
		"""
		Adds a new Pub/Sub channel to the subscription.

		:param channel: a Redis Pub/Sub channel
		"""
		if self.closed:
			raise Exception("tried to use a closed ChannelSubscription")

		channel = as_bytes(channel)
		if channel in self.channels:
			return

		fn_box = Box(self.on_message, self.on_activation)
		self.channels[channel] = fn_box
		self.mpx._add(channel, fn_box)

	def remove(self, channel: Union[str, bytes]) -> None:
		"""
		Removes a Redis Pub/Sub channel from the subscription.

		:param channel: a Redis Pub/Sub channel
		"""
		if self.closed:
			raise Exception("tried to use a closed ChannelSubscription")

		channel = as_bytes(channel)

		if channel not in self.channels:
			return
		fn_box = self.channels.pop(channel)
		self.mpx._remove(channel, fn_box)

	def close(self) -> None:
		"""Closes the subscription."""

		if self.closed:
			raise Exception("tried to use a closed ChannelSubscription")

		while len(self.channels) > 0:
			ch, fn_box = self.channels.popitem()
			self.mpx._remove(ch, fn_box)
		self.closed = True
		self.mpx._remove_subscription(self)
