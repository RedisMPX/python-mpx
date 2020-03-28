from aioredis.abc import AbcConnection
from aioredis.parser import Reader
from aioredis.errors import (
    ConnectionClosedError,
    ConnectionForcedCloseError,
    RedisError,
    ProtocolError,
    ReplyError,
    WatchVariableError,
    ReadOnlyError,
    MaxClientsError
)


class Conn(AbcConnection):
    def __init__(self, reader, writer, *, address, encoding=None,
                     parser=None, loop=None):
        if parser is None:
            parser = Reader

        self._reader = reader
        self._writer = writer
        self._address = address
        self._reader.set_parser(
            parser(protocolError=ProtocolError, replyError=ReplyError)
        )

    def write_command(self, *args):
        self._writer.write(encode_command(*args))

    def drain(self):
        return self._writer.drain()

    async def read_message(self):
        while not self._reader.at_eof():
            obj = await self._reader.readobj()
            if (obj == b'' or obj is None) and self._reader.at_eof():
                raise Exception("reached EOF") 
            if isinstance(obj, MaxClientsError):
                raise MaxClientsError()
            yield obj
        raise Exception("reached EOF") 

    def execute(self, command, *args, **kwargs):
        raise NotImplemented
    def execute_pubsub(self, command, *args, **kwargs):
        raise NotImplemented

    def close(self):
        pass   

    async def wait_closed(self):
        raise NotImplemented

    @property
    def closed(self):
        raise NotImplemented

    @property
    def db(self):
        raise NotImplemented

    @property
    def encoding(self):
        raise NotImplemented

    @property
    def in_pubsub(self):
        raise NotImplemented

    @property
    def pubsub_channels(self):
        raise NotImplemented

    @property
    def pubsub_patterns(self):
        raise NotImplemented

    @property
    def address(self):
        raise NotImplemented


def encode_command(*args):
    buf = bytearray()
    buf.extend(b'*%d\r\n' % len(args))
    for arg in args:
        buf.extend(b'$%d\r\n%s\r\n' % (len(arg), arg))
    return buf
