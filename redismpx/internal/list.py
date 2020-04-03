class List:
    def __init__(self, head: 'ListNode'):
        if head is not None:
            head._list = self
        self._head = head

    def prepend(self, node: 'ListNode') -> None:
        node._list = self
        if self._head is None:
            self._head = node
        else:
            self._head._prev = node
            node.next = self._head
            self._head = node

    def is_empty(self) -> bool:
        return self._head is None

    def __iter__(self) -> 'ListIterator':
        return ListIterator(self._head)

class ListNode:
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])
            self._next = None
            self._prev = None
            self._list = None

    def remove_from_list(self) -> List:
        l = self._list

        if l._head is self:
            l._head = self._next

        if self._next:
            self._next._prev = self._prev

        if self._prev:
            self._prev._next = self._next

        self._list = None
        self._next = None
        self._prev = None

        return l

class ListIterator:
    def __init__(self, node):
        self.next = node

    def __next__(self):
        if self.next is None:
            raise StopIteration
        n = self.next
        self.next = self.next._next
        return n