import pytest
import asyncio
from redismpx import Multiplexer

@pytest.mark.asyncio
async def test_multiplexer():
	mpx = Multiplexer("redis://localhost")
	await asyncio.wait_for(mpx.connected_event.wait(), 3)
	mpx.close()
