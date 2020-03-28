import random
from collections import namedtuple

class SubscriptionIsClosed(Exception):
	pass

Box = namedtuple('CallbackBox', ['on_message', 'on_activation'])

def as_bytes(string):
	if isinstance(string, bytes):
		return string
	return string.encode()

def jitter_exp_backoff(base, max, attempts):
	return andom.randint(0, min(max, base * 2 ** attempts))