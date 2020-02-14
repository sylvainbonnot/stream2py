__all__ = ['BufferReader']

import threading

from stream2py.utility.locked_sorted_deque import RWLockSortedDeque


class BufferReader:
    """Reader that is constructed from StreamBuffer.mk_reader()"""

    def __init__(self, buffer: RWLockSortedDeque, source_reader_info: dict, stop_event: threading.Event):
        """

        :param buffer:
        :param source_reader_info:
        :param stop_event: threading.Event for source read loop
        """
        assert isinstance(buffer, RWLockSortedDeque)
        assert isinstance(stop_event, threading.Event)

        self._source_reader_info = source_reader_info
        self._buffer = buffer
        self._last_item = None
        self._last_key = None
        self._stop_event = stop_event

    def __hash__(self):
        return hash(self._stop_event)

    def __eq__(self, other):
        """BufferReaders are equivalent if they share a stop event
        and thus the same source instance/session and buffer"""
        return self.__class__ == other.__class__ and self._stop_event == other._stop_event

    def __ne__(self, other):
        return not self == other

    @property
    def is_stopped(self) -> bool:
        """Checks if stop event has been set by StreamBuffer.

        :return: bool
        """
        return self._stop_event.is_set()

    @property
    def source_reader_info(self) -> dict:
        """A dict with important source info set by SourceReader.

        :return: dict
        """
        return self._source_reader_info

    @property
    def last_key(self):
        return self._last_key

    def _getlast_item(self):
        return self._last_item

    def _setlast_item(self, item):
        self._last_key = self._buffer.key(item)
        self._last_item = item

    def _dellast_item(self):
        del self._last_item
        self._last_item = None
        del self._last_key
        self._last_key = None

    last_item = property(_getlast_item, _setlast_item, _dellast_item, 'last_item cursor')

    def next(self, *, peek=False, ignore_no_item_found=False):
        """Finds an item with a key greater than the last returned item.
        Raise ValueError if no item found with key above last item.

        :param peek: if True, last_item cursor will not be updated
        :param ignore_no_item_found: if True, return None when no next item instead of raising exception
        :return: next item
        """
        with self._buffer.reader_lock() as reader:
            try:
                next_item = reader.find_gt(self.last_key)
            except ValueError as e:  # ValueError: No item found with key above: self.last_key
                if ignore_no_item_found:
                    return None
                else:
                    raise e
            except TypeError as e:  # TypeError: '<' not supported between instances of 'NoneType' and type(key)
                if self.last_item is None:  # first time reading a value from buffer
                    next_item = reader[0]
                else:
                    raise e
        if not peek:
            self.last_item = next_item
        return next_item

    def range(self, start, stop, step=None, *, peek=False, ignore_no_item_found=False, only_new_items=False):
        """Enables:
        1. Get last n minutes
        2. Give me data I don't have

        :param start: starting range key of item
        :param stop: ending range key of item
        :param step:
        :param peek: if True, last_item cursor will not be updated
        :param ignore_no_item_found: if True, return None when no next item instead of raising exception
        :param only_new_items: if True and no new items, raise ValueError or return None if ignore_no_item_found
        :return: list of items in range
        """
        with self._buffer.reader_lock() as reader:
            if only_new_items and self.last_key is not None:
                _next_key = reader.key(self.next(peek=True, ignore_no_item_found=ignore_no_item_found))
                _start = start if start > _next_key else _next_key
            else:
                _start = start
            items = reader.range(_start, stop, step)

        if not peek:
            try:
                self.last_item = items[-1]
            except IndexError as e:  # IndexError: list index out of range
                if ignore_no_item_found:
                    return None
                else:
                    raise e
        return items

    def tail(self, *, peek=False, ignore_no_item_found=False, only_new_items=False):
        """Finds the last item in buffer. Raise ValueError if no item found.

        :param peek: if True, last_item cursor will not be updated
        :param ignore_no_item_found: if True, return None when no next item instead of raising exception
        :param only_new_items: if True and no new items, raise ValueError or return None if ignore_no_item_found
        :return: tail item
        """
        with self._buffer.reader_lock() as reader:
            if only_new_items:
                try:
                    item = reader.find_last_gt(self.last_key)
                except ValueError as e:  # ValueError: No item found with key above: self.last_key
                    if ignore_no_item_found:
                        return None
                    else:
                        raise e
                except TypeError as e:  # TypeError: '>' not supported between instances of type(key) and 'NoneType'
                    if self.last_item is None:  # first time reading a value from buffer
                        item = reader[-1]
                    else:
                        raise e
            else:
                try:
                    item = reader[-1]
                except IndexError as e:  # IndexError: deque index out of range
                    if ignore_no_item_found:
                        return None
                    else:
                        raise e
        if not peek:
            self.last_item = item
        return item

    def head(self, *, peek=False):
        with self._buffer.reader_lock() as reader:
            item = reader[0]
        if not peek:
            self.last_item = item
        return item