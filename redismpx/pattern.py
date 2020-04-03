from typing import Union
from .utils import as_bytes, SubscriptionIsClosed
from .internal import ListNode

class PatternSubscription:
	"""
	A PatternSubscription ties a on_message callback to one Redis Pub/Sub pattern.
	Use :func:`~redismpx.Multiplexer.new_pattern_subscription` to create a new 
	PatternSubscription.

	Usage example:

	.. highlight:: python

    .. code-block:: python
	
		# This subscription will receive all messages sent to 
		# channels that start with "red", like `redis` and `reddit`.
		pattern_sub = mpx.new_pattern_subscription("red*", 
			my_on_message, my_on_disconnect, my_on_activation)

		# Once created, a PatternSubscription can only be closed.
		pattern_sub.close()

	"""
	def __init__(self, multiplexer, pattern, on_message, on_disconnect, on_activation):
		pattern = as_bytes(pattern)

		self.channels = {}
		self.mpx = multiplexer
		self.pattern = pattern
		self.fn_box =  ListNode(on_message=on_message, on_activation=on_activation)
		self.on_disconnect = on_disconnect
		self.on_activation = on_activation
		self.closed = False
		self.subNode = ListNode(on_disconnect=on_disconnect)
		self.mpx.subscriptions.prepend(self.subNode)
		self.mpx._add_pattern(pattern, self.fn_box)

	def close(self) -> None:
		"""Closes the subscription."""
		if self.closed:
			raise SubscriptionIsClosed("tried to use a closed PatternSubscription")
			
		self.mpx._remove_pattern(self.pattern, self.fn_box)
		self.subNode.remove_from_list()
		self.closed = True

