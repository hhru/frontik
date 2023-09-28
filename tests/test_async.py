from __future__ import annotations
from tornado.concurrent import Future
from tornado.testing import AsyncTestCase
from typing import TYPE_CHECKING
from frontik.futures import future_fold

if TYPE_CHECKING:
    from asyncio import Future
    from typing import Callable, Optional, Tuple, Type, Union


class MyException(Exception):
    def __init__(self, result_was: Optional[object]=None) -> None:
        self.result_was = result_was


class MyOtherException(MyException):
    pass


class TestFutureFold(AsyncTestCase):
    def test_value_to_value(self):
        marker = object()
        result_marker = object()

        future: Future = Future()
        future_probe = FutureProbe(future)

        def _mapper(result):
            return marker, result

        res_future = future_fold(future, result_mapper=_mapper)
        check_res_future = FutureProbe(res_future, stop_cb=self.stop)

        future.set_result(result_marker)
        self.wait()

        future_probe.assert_single_result_call(self, result_marker)
        check_res_future.assert_single_result_call(self, (marker, result_marker))

    def test_value_to_exception(self):
        result_marker = object()
        future: Future = Future()
        future_probe = FutureProbe(future)

        def _mapper(result):
            raise MyException(result_was=result)

        res_future = future_fold(future, result_mapper=_mapper)
        res_future_probe = FutureProbe(res_future, stop_cb=self.stop)

        future.set_result(result_marker)
        self.wait()

        future_probe.assert_single_result_call(self, result_marker)
        res_future_probe.assert_single_exception_call(self, MyException, result_marker)

    def test_exception_to_value(self):
        marker = object()

        future: Future = Future()
        future_probe = FutureProbe(future)

        def _exception_mapper(exception):
            # We need to check exception type, but here we can't raise AssertionException.
            # So it returns None for failing in assertions bellow.
            if isinstance(exception, MyException):
                return marker
            else:
                return None

        res_future = future_fold(future, exception_mapper=_exception_mapper)
        res_future_probe = FutureProbe(res_future, stop_cb=self.stop)

        future.set_exception(MyException())
        self.wait()

        future_probe.assert_single_exception_call(self, MyException)
        res_future_probe.assert_single_result_call(self, marker)

    def test_exception_to_exception(self):
        future: Future = Future()
        future_probe = FutureProbe(future)

        def _exception_mapper(exception):
            if isinstance(exception, MyException):
                raise MyOtherException()
            else:
                return None

        res_future = future_fold(future, exception_mapper=_exception_mapper)
        res_future_probe = FutureProbe(res_future, stop_cb=self.stop)

        future.set_exception(MyException())
        self.wait()

        future_probe.assert_single_exception_call(self, MyException)
        res_future_probe.assert_single_exception_call(self, MyOtherException)

    def test_both(self):
        marker = object()
        second_marker = object()
        result_marker = object()

        def _mapper(_):
            return marker

        def _exception_mapper(_):
            return second_marker

        first_future: Future = Future()
        folded_future = future_fold(first_future, result_mapper=_mapper, exception_mapper=_exception_mapper)
        folded_future_probe = FutureProbe(folded_future)

        second_future: Future = Future()
        second_folded_future = future_fold(second_future, result_mapper=_mapper, exception_mapper=_exception_mapper)
        second_folded_future_probe = FutureProbe(second_folded_future, stop_cb=self.stop)

        first_future.set_result(result_marker)
        second_future.set_exception(MyException())
        self.wait()

        folded_future_probe.assert_single_result_call(self, marker)
        second_folded_future_probe.assert_single_result_call(self, second_marker)


class FutureProbe:
    _DEFAULT = object

    def __init__(self, future_to_check: Future, stop_cb: Optional[Callable]=None) -> None:
        self._calls: list = []
        self._stop_cb = stop_cb
        future_to_check.add_done_callback(self.build_callback())

    def build_callback(self) -> Callable:
        def _cb(future):
            exception = future.exception()
            result = None
            if exception is None:
                result = future.result()
            self._calls.append((result, exception))
            if callable(self._stop_cb):
                self._stop_cb()
        return _cb

    def assert_single_result_call(self, test: TestFutureFold, expected_result: Union[Tuple[object, object], object]) -> None:
        test.assertEqual(len(self._calls), 1, msg='should be only one future resolve')
        test.assertEqual(self._calls[0][0], expected_result, msg='expected future result not matched')

    def assert_single_exception_call(self, test: TestFutureFold, expected_exception_class: Union[Type[MyException], Type[MyOtherException]], result_was: Union[Type[object], object]=_DEFAULT) -> None:
        assert issubclass(expected_exception_class, MyException)

        test.assertEqual(len(self._calls), 1, msg='should be only one future resolve with exception')
        exception = self._calls[0][1]
        test.assertIsInstance(exception, expected_exception_class,
                              msg='exception should have expected type')
        if result_was is not self._DEFAULT:
            test.assertEqual(exception.result_was, result_was)