import random

class SubscriptionIsClosed(Exception):
	pass

def as_bytes(string):
	if isinstance(string, bytes):
		return string
	return string.encode()

def jitter_exp_backoff(base, maxValue, attempts):
	return random.randint(0, min(maxValue, base * 2 ** attempts))