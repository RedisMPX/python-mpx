import pytest
import asyncio
import aioredis
from redismpx import Multiplexer

@pytest.mark.asyncio
async def test_channel():
    mpx = Multiplexer("redis://localhost")
    pub_conn = await aioredis.create_connection('redis://localhost')
        
    active = asyncio.Event()

    messages = []
    errors = []
    activations = []
    channel_subscription = mpx.new_channel_subscription(
        lambda c, m: messages.append(m),
        lambda e: errors.append(active.clear()),
        lambda a: activations.append(active.set()))

    channel_subscription.add('test1')
    await asyncio.wait_for(active.wait(), 3)

    await pub_conn.execute("client", "kill", "type", "pubsub")
    await asyncio.wait_for(active.wait(), 3)

    assert len(activations) == 2
    assert len(errors) == 1

    mpx.close()
    pub_conn.close()
