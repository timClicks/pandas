cimport numpy as np
cimport cython

from numpy cimport *

from cpython cimport (PyDict_New, PyDict_GetItem, PyDict_SetItem,
                          PyDict_Contains, PyDict_Keys)
from cpython cimport PyFloat_Check

import numpy as np
isnan = np.isnan
cdef double NaN = <double> np.NaN
cdef double nan = NaN

from datetime import datetime as pydatetime

cdef inline int int_max(int a, int b): return a if a >= b else b
cdef inline int int_min(int a, int b): return a if a <= b else b

ctypedef unsigned char UChar

cdef int is_contiguous(ndarray arr):
    return np.PyArray_CHKFLAGS(arr, np.NPY_C_CONTIGUOUS)

cdef int _contiguous_check(ndarray arr):
    if not is_contiguous(arr):
        raise ValueError('Tried to use data field on non-contiguous array!')

cdef int16_t *get_int16_ptr(ndarray arr):
    _contiguous_check(arr)

    return <int16_t *> arr.data

cdef int32_t *get_int32_ptr(ndarray arr):
    _contiguous_check(arr)

    return <int32_t *> arr.data

cdef int64_t *get_int64_ptr(ndarray arr):
    _contiguous_check(arr)

    return <int64_t *> arr.data

cdef double_t *get_double_ptr(ndarray arr):
    _contiguous_check(arr)

    return <double_t *> arr.data

cdef extern from "math.h":
    double sqrt(double x)

cdef extern from "cobject.h":
    pass # for datetime API

cdef extern from "datetime.h":

    ctypedef class datetime.datetime [object PyDateTime_DateTime]:
        # cdef int *data
        # cdef long hashcode
        # cdef char hastzinfo
        pass

    int PyDateTime_GET_YEAR(datetime o)
    int PyDateTime_GET_MONTH(datetime o)
    int PyDateTime_GET_DAY(datetime o)
    int PyDateTime_DATE_GET_HOUR(datetime o)
    int PyDateTime_DATE_GET_MINUTE(datetime o)
    int PyDateTime_DATE_GET_SECOND(datetime o)
    int PyDateTime_DATE_GET_MICROSECOND(datetime o)
    int PyDateTime_TIME_GET_HOUR(datetime o)
    int PyDateTime_TIME_GET_MINUTE(datetime o)
    int PyDateTime_TIME_GET_SECOND(datetime o)
    int PyDateTime_TIME_GET_MICROSECOND(datetime o)
    bint PyDateTime_Check(object o)
    void PyDateTime_IMPORT()

# import datetime C API
PyDateTime_IMPORT

# initialize numpy
import_array()

cpdef map_indices(ndarray index):
    '''
    Produce a dict mapping the values of the input array to their respective
    locations.

    Example:
        array(['hi', 'there']) --> {'hi' : 0 , 'there' : 1}

    Better to do this with Cython because of the enormous speed boost.
    '''
    cdef int i, length
    cdef flatiter iter
    cdef dict result
    cdef object idx

    result = {}

    iter = <flatiter> PyArray_IterNew(index)
    length = PyArray_SIZE(index)

    for i from 0 <= i < length:
        idx = PyArray_GETITEM(index, PyArray_ITER_DATA(iter))
        result[idx] = i
        PyArray_ITER_NEXT(iter)

    return result

cpdef map_indices_buf(ndarray[object] index):
    '''
    Produce a dict mapping the values of the input array to their respective
    locations.

    Example:
        array(['hi', 'there']) --> {'hi' : 0 , 'there' : 1}

    Better to do this with Cython because of the enormous speed boost.
    '''
    cdef Py_ssize_t i, length
    cdef dict result = {}

    length = len(index)

    for i from 0 <= i < length:
        result[index[i]] = i

    return result

cpdef map_indices_list(list index):
    '''
    Produce a dict mapping the values of the input array to their respective
    locations.

    Example:
        array(['hi', 'there']) --> {'hi' : 0 , 'there' : 1}

    Better to do this with Cython because of the enormous speed boost.
    '''
    cdef Py_ssize_t i, length
    cdef dict result = {}

    length = len(index)

    for i from 0 <= i < length:
        result[index[i]] = i

    return result

from libc.stdlib cimport malloc, free

cdef class MultiMap:
    '''
    Need to come up with a better data structure for multi-level indexing
    '''

    cdef:
        dict store
        Py_ssize_t depth, length

    def __init__(self, list label_arrays):
        cdef:
            int32_t **ptr
            Py_ssize_t i

        self.depth = len(label_arrays)
        self.length = len(label_arrays[0])
        self.store = {}

        ptr = <int32_t**> malloc(self.depth * sizeof(int32_t*))

        for i in range(self.depth):
            ptr[i] = <int32_t*> (<ndarray> label_arrays[i]).data

        free(ptr)

    cdef populate(self, int32_t **ptr):
        cdef Py_ssize_t i, j
        cdef int32_t* buf
        cdef dict level

        for i from 0 <= i < self.length:

            for j from 0 <= j < self.depth - 1:
                pass

    cpdef get(self, tuple key):
        cdef Py_ssize_t i
        cdef dict level = self.store

        for i from 0 <= i < self.depth:
            if i == self.depth - 1:
                return level[i]
            else:
                level = level[i]

        raise KeyError(key)


def isAllDates(ndarray index):
    cdef int i, length
    cdef flatiter iter
    cdef object date

    iter = <flatiter> PyArray_IterNew(index)
    length = PyArray_SIZE(index)

    if length == 0:
        return False

    for i from 0 <= i < length:
        date = PyArray_GETITEM(index, PyArray_ITER_DATA(iter))

        if not PyDateTime_Check(date):
            return False
        PyArray_ITER_NEXT(iter)

    return True

def isAllDates2(ndarray[object, ndim=1] arr):
    '''
    cannot use
    '''

    cdef int i, size = len(arr)
    cdef object date

    if size == 0:
        return False

    for i from 0 <= i < size:
        date = arr[i]

        if not PyDateTime_Check(date):
            return False

    return True

cdef double __add(double a, double b):
    return a + b
cdef double __sub(double a, double b):
    return a - b

cdef double __div(double a, double b):
    if b == 0:
        return NaN
    else:
        return a / b

cdef double __mul(double a, double b):
    return a * b
cdef double __eq(double a, double b):
    return a == b
cdef double __ne(double a, double b):
    return a != b
cdef double __lt(double a, double b):
    return a < b
cdef double __gt(double a, double b):
    return a > b

cdef double __pow(double a, double b):
    # NaN
    if a != a or b != b:
        return NaN
    return a ** b

ctypedef double (* double_func)(double a, double b)

