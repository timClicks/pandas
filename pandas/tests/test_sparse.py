# pylint: disable-msg=E1101,W0612

from unittest import TestCase
import cPickle as pickle
import operator

import nose

from numpy import nan
import numpy as np
dec = np.testing.dec

from pandas.util.testing import (assert_almost_equal, assert_series_equal,
                                 assert_frame_equal, assert_panel_equal)
from numpy.testing import assert_equal

from pandas import Series, DataFrame, DateRange, WidePanel
from pandas.core.datetools import BDay
from pandas.core.series import remove_na
import pandas.core.datetools as datetools
import pandas.util.testing as testing

import pandas.core.sparse as spm
reload(spm)
from pandas.core.sparse import (IntIndex, BlockIndex,
                                SparseSeries, SparseDataFrame,
                                SparseWidePanel)

import test_panel


"""
Testing TODO


"""
def _test_data1():
    # nan-based
    arr = np.arange(20, dtype=float)
    index = np.arange(20)
    arr[:2] = nan
    arr[5:10] = nan
    arr[-3:] = nan

    return arr, index

def _test_data2():
    # nan-based
    arr = np.arange(15, dtype=float)
    index = np.arange(15)
    arr[7:12] = nan
    arr[-1:] = nan
    return arr, index

def _test_data1_zero():
    # zero-based
    arr, index = _test_data1()
    arr[np.isnan(arr)] = 0
    return arr, index

def _test_data2_zero():
    # zero-based
    arr, index = _test_data2()
    arr[np.isnan(arr)] = 0
    return arr, index

def assert_sp_series_equal(a, b):
    assert_equal(a.sp_values, b.sp_values)
    assert(a.sp_index.equals(b.sp_index))
    if np.isnan(a.fill_value):
        assert(np.isnan(b.fill_value))
    else:
        assert(a.fill_value == b.fill_value)

def assert_sp_frame_equal(left, right, exact_indices=True):
    """
    exact: Series SparseIndex objects must be exactly the same, otherwise just
    compare dense representations
    """
    for col, series in left.iteritems():
        assert(col in right)
        # trade-off?

        if exact_indices:
            assert_sp_series_equal(series, right[col])
        else:
            assert_series_equal(series.to_dense(), right[col].to_dense())

    assert_almost_equal(left.default_fill_value,
                        right.default_fill_value)

    # do I care?
    # assert(left.default_kind == right.default_kind)

    for col in right:
        assert(col in left)

def assert_sp_panel_equal(left, right, exact_indices=True):
    for item, frame in left.iteritems():
        assert(item in right)
        # trade-off?
        assert_sp_frame_equal(frame, right[item], exact_indices=exact_indices)

    assert_almost_equal(left.default_fill_value,
                        right.default_fill_value)
    assert(left.default_kind == right.default_kind)

    for item in right:
        assert(item in left)

class TestSparseSeries(TestCase):

    def setUp(self):
        arr, index = _test_data1()

        date_index = DateRange('1/1/2011', periods=len(index))

        self.bseries = SparseSeries(arr, index=index, kind='block')
        self.btseries = SparseSeries(arr, index=date_index, kind='block')

        self.iseries = SparseSeries(arr, index=index, kind='integer')

        arr, index = _test_data2()
        self.bseries2 = SparseSeries(arr, index=index, kind='block')
        self.iseries2 = SparseSeries(arr, index=index, kind='integer')

        arr, index = _test_data1_zero()
        self.zbseries = SparseSeries(arr, index=index, kind='block',
                                     fill_value=0)
        self.ziseries = SparseSeries(arr, index=index, kind='integer',
                                     fill_value=0)

        arr, index = _test_data2_zero()
        self.zbseries2 = SparseSeries(arr, index=index, kind='block',
                                      fill_value=0)
        self.ziseries2 = SparseSeries(arr, index=index, kind='integer',
                                      fill_value=0)

    def test_sparse_to_dense(self):
        arr, index = _test_data1()
        series = self.bseries.to_dense()
        assert_equal(series, arr)

        series = self.bseries.to_dense(sparse_only=True)
        assert_equal(series, arr[np.isfinite(arr)])

        series = self.iseries.to_dense()
        assert_equal(series, arr)

        arr, index = _test_data1_zero()
        series = self.zbseries.to_dense()
        assert_equal(series, arr)

        series = self.ziseries.to_dense()
        assert_equal(series, arr)

    def test_dense_to_sparse(self):
        series = self.bseries.to_dense()
        bseries = series.to_sparse(kind='block')
        iseries = series.to_sparse(kind='integer')
        assert_sp_series_equal(bseries, self.bseries)
        assert_sp_series_equal(iseries, self.iseries)

        # non-NaN fill value
        series = self.zbseries.to_dense()
        zbseries = series.to_sparse(kind='block', fill_value=0)
        ziseries = series.to_sparse(kind='integer', fill_value=0)
        assert_sp_series_equal(zbseries, self.zbseries)
        assert_sp_series_equal(ziseries, self.ziseries)

    def test_constructor(self):
        # test setup guys
        self.assert_(np.isnan(self.bseries.fill_value))
        self.assert_(isinstance(self.bseries.sp_index, BlockIndex))
        self.assert_(np.isnan(self.iseries.fill_value))
        self.assert_(isinstance(self.iseries.sp_index, IntIndex))

        self.assertEquals(self.zbseries.fill_value, 0)
        assert_equal(self.zbseries.values, self.bseries.to_dense().fillna(0))

        # pass SparseSeries
        s2 = SparseSeries(self.bseries)
        s3 = SparseSeries(self.iseries)
        s4 = SparseSeries(self.zbseries)
        assert_sp_series_equal(s2, self.bseries)
        assert_sp_series_equal(s3, self.iseries)
        assert_sp_series_equal(s4, self.zbseries)

        # Sparse time series works
        date_index = DateRange('1/1/2000', periods=len(self.bseries))
        s5 = SparseSeries(self.bseries, index=date_index)
        self.assert_(isinstance(s5, spm.SparseTimeSeries))

        # pass Series
        bseries2 = SparseSeries(self.bseries.to_dense())
        assert_equal(self.bseries.sp_values, bseries2.sp_values)

        # pass dict

        # don't copy the data by default
        values = np.ones(len(self.bseries.sp_values))
        sp = SparseSeries(values, sparse_index=self.bseries.sp_index)
        sp.sp_values[:5] = 97
        self.assert_(values[0] == 97)

        # but can make it copy!
        sp = SparseSeries(values, sparse_index=self.bseries.sp_index,
                          copy=True)
        sp.sp_values[:5] = 100
        self.assert_(values[0] == 97)

    def test_constructor_ndarray(self):
        pass

    def test_constructor_nonnan(self):
        arr = [0, 0, 0, nan, nan]
        sp_series = SparseSeries(arr, fill_value=0)
        assert_equal(sp_series.values, arr)

    def test_copy_astype(self):
        cop = self.bseries.astype(np.int32)
        self.assert_(cop is not self.bseries)
        self.assert_(cop.sp_index is self.bseries.sp_index)
        self.assert_(cop.dtype == np.float64)

        cop2 = self.iseries.copy()

        assert_sp_series_equal(cop, self.bseries)
        assert_sp_series_equal(cop2, self.iseries)

        # test that data is copied
        cop.sp_values[:5] = 97
        self.assert_(cop.sp_values[0] == 97)
        self.assert_(self.bseries.sp_values[0] != 97)

        # correct fill value
        zbcop = self.zbseries.copy()
        zicop = self.ziseries.copy()

        assert_sp_series_equal(zbcop, self.zbseries)
        assert_sp_series_equal(zicop, self.ziseries)

    def test_kind(self):
        self.assertEquals(self.bseries.kind, 'block')
        self.assertEquals(self.iseries.kind, 'integer')

    def test_pickle(self):
        def _test_roundtrip(series):
            pickled = pickle.dumps(series, protocol=pickle.HIGHEST_PROTOCOL)
            unpickled = pickle.loads(pickled)
            assert_sp_series_equal(series, unpickled)
            assert_series_equal(series.to_dense(), unpickled.to_dense())

        self._check_all(_test_roundtrip)

    def _check_all(self, check_func):
        check_func(self.bseries)
        check_func(self.iseries)
        check_func(self.zbseries)
        check_func(self.ziseries)

    def test_getitem(self):
        def _check_getitem(sp, dense):
            for idx, val in dense.iteritems():
                assert_almost_equal(val, sp[idx])

            for i in xrange(len(dense)):
                assert_almost_equal(sp[i], dense[i])
                # j = np.float64(i)
                # assert_almost_equal(sp[j], dense[j])

            # negative getitem works
            for i in xrange(len(dense)):
                assert_almost_equal(sp[-i], dense[-i])

        _check_getitem(self.bseries, self.bseries.to_dense())
        _check_getitem(self.btseries, self.btseries.to_dense())

        _check_getitem(self.zbseries, self.zbseries.to_dense())
        _check_getitem(self.iseries, self.iseries.to_dense())
        _check_getitem(self.ziseries, self.ziseries.to_dense())

        # exception handling
        self.assertRaises(Exception, self.bseries.__getitem__,
                          len(self.bseries) + 1)

        # index not contained
        self.assertRaises(Exception, self.btseries.__getitem__,
                          self.btseries.index[-1] + BDay())

    def test_get(self):
        assert_almost_equal(self.bseries.get(10), self.bseries[10])
        self.assert_(self.bseries.get(len(self.bseries) + 1) is None)

    def test_getitem_fancy_index(self):
        idx = self.bseries.index
        res = self.bseries[::2]
        self.assert_(isinstance(res, SparseSeries))
        assert_sp_series_equal(res, self.bseries.reindex(idx[::2]))

        res = self.bseries[:5]
        self.assert_(isinstance(res, SparseSeries))
        assert_sp_series_equal(res, self.bseries.reindex(idx[:5]))

        res = self.bseries[5:]
        assert_sp_series_equal(res, self.bseries.reindex(idx[5:]))

    def test_take(self):
        def _compare_with_dense(sp):
            dense = sp.to_dense()

            def _compare(idx):
                dense_result = dense.take(idx)
                sparse_result = sp.take(idx)
                assert_almost_equal(dense_result, sparse_result)

            _compare([1., 2., 3., 4., 5., 0.])
            _compare([7, 2, 9, 0, 4])
            _compare([3, 6, 3, 4, 7])

        self._check_all(_compare_with_dense)

        self.assertRaises(Exception, self.bseries.take, [-1, 0])
        self.assertRaises(Exception, self.bseries.take,
                          [0, len(self.bseries) + 1])

        # Corner case
        sp = SparseSeries(np.ones(10.) * nan)
        assert_almost_equal(sp.take([0, 1, 2, 3, 4]), np.repeat(nan, 5))

    def test_getslice(self):
        pass

    def test_setitem(self):
        self.assertRaises(Exception, self.bseries.__setitem__, 5, 7.)
        self.assertRaises(Exception, self.iseries.__setitem__, 5, 7.)

    def test_setslice(self):
        self.assertRaises(Exception, self.bseries.__setslice__, 5, 10, 7.)

    def test_operators(self):
        def _check_op(a, b, op):
            sp_result = op(a, b)
            adense = a.to_dense() if isinstance(a, SparseSeries) else a
            bdense = b.to_dense() if isinstance(b, SparseSeries) else b
            dense_result = op(adense, bdense)
            assert_almost_equal(sp_result.to_dense(), dense_result)

        def check(a, b):
            _check_op(a, b, operator.add)
            _check_op(a, b, operator.sub)
            _check_op(a, b, operator.div)
            _check_op(a, b, operator.mul)

            _check_op(a, b, lambda x, y: operator.add(y, x))
            _check_op(a, b, lambda x, y: operator.sub(y, x))
            _check_op(a, b, lambda x, y: operator.div(y, x))
            _check_op(a, b, lambda x, y: operator.mul(y, x))

            # NaN ** 0 = 1 in C?
            # _check_op(a, b, operator.pow)
            # _check_op(a, b, lambda x, y: operator.pow(y, x))

        check(self.bseries, self.bseries)
        check(self.iseries, self.iseries)
        check(self.bseries, self.iseries)

        check(self.bseries, self.bseries2)
        check(self.bseries, self.iseries2)
        check(self.iseries, self.iseries2)

        # scalar value
        check(self.bseries, 5)

        # zero-based
        check(self.zbseries, self.zbseries * 2)
        check(self.zbseries, self.zbseries2)
        check(self.ziseries, self.ziseries2)

        # with dense
        result = self.bseries + self.bseries.to_dense()
        assert_sp_series_equal(result, self.bseries + self.bseries)

    # @dec.knownfailureif(True, 'Known NumPy failer as of 1.5.1')
    def test_operators_corner2(self):
        raise nose.SkipTest('known failer on numpy 1.5.1')

        # NumPy circumvents __r*__ operations
        val = np.float64(3.0)
        result = val - self.zbseries
        assert_sp_series_equal(result, 3 - self.zbseries)

    def test_reindex(self):
        def _compare_with_series(sps, new_index):
            spsre = sps.reindex(new_index)

            series = sps.to_dense()
            seriesre = series.reindex(new_index)
            seriesre = seriesre.to_sparse(fill_value=sps.fill_value)

            assert_sp_series_equal(spsre, seriesre)
            assert_series_equal(spsre.to_dense(), seriesre.to_dense())

        _compare_with_series(self.bseries, self.bseries.index[::2])
        _compare_with_series(self.bseries, list(self.bseries.index[::2]))
        _compare_with_series(self.bseries, self.bseries.index[:10])
        _compare_with_series(self.bseries, self.bseries.index[5:])

        _compare_with_series(self.zbseries, self.zbseries.index[::2])
        _compare_with_series(self.zbseries, self.zbseries.index[:10])
        _compare_with_series(self.zbseries, self.zbseries.index[5:])

        # special cases
        same_index = self.bseries.reindex(self.bseries.index)
        assert_sp_series_equal(self.bseries, same_index)
        self.assert_(same_index is not self.bseries)

        # corner cases
        sp = SparseSeries([], index=[])
        sp_zero = SparseSeries([], index=[], fill_value=0)
        _compare_with_series(sp, np.arange(10))

    def test_sparse_reindex(self):
        length = 10

        def _check(values, index1, index2, fill_value):
            first_series = SparseSeries(values, sparse_index=index1,
                                        fill_value=fill_value)
            reindexed = first_series.sparse_reindex(index2)
            self.assert_(reindexed.sp_index is index2)

            int_indices1 = index1.to_int_index().indices
            int_indices2 = index2.to_int_index().indices

            expected = Series(values, index=int_indices1)
            expected = expected.reindex(int_indices2).fillna(fill_value)
            assert_almost_equal(expected.values, reindexed.sp_values)

        def _check_with_fill_value(values, first, second, fill_value=nan):
            i_index1 = IntIndex(length, first)
            i_index2 = IntIndex(length, second)

            b_index1 = i_index1.to_block_index()
            b_index2 = i_index2.to_block_index()

            _check(values, i_index1, i_index2, fill_value)
            _check(values, b_index1, b_index2, fill_value)

        def _check_all(values, first, second):
            _check_with_fill_value(values, first, second, fill_value=nan)
            _check_with_fill_value(values, first, second, fill_value=0)

        index1 = [2, 4, 5, 6, 8, 9]
        values1 = np.arange(6.)

        _check_all(values1, index1, [2, 4, 5])
        _check_all(values1, index1, [2, 3, 4, 5, 6, 7, 8, 9])
        _check_all(values1, index1, [0, 1])
        _check_all(values1, index1, [0, 1, 7, 8, 9])
        _check_all(values1, index1, [])

    def test_repr(self):
        bsrepr = repr(self.bseries)
        isrepr = repr(self.iseries)

    def test_iter(self):
        pass

    def test_truncate(self):
        pass

    def test_fillna(self):
        pass

    def test_groupby(self):
        pass

    def test_reductions(self):
        def _compare_with_dense(obj, op):
            sparse_result = getattr(obj, op)()
            series = obj.to_dense()
            dense_result = getattr(series, op)()
            self.assertEquals(sparse_result, dense_result)

        to_compare = ['count', 'sum', 'mean', 'std', 'var', 'skew']
        def _compare_all(obj):
            for op in to_compare:
                _compare_with_dense(obj, op)

        _compare_all(self.bseries)
        self.bseries.sp_values[5:10] = np.NaN
        _compare_all(self.bseries)

        _compare_all(self.zbseries)
        self.zbseries.sp_values[5:10] = np.NaN
        _compare_all(self.zbseries)

        series = self.zbseries.copy()
        series.fill_value = 2
        _compare_all(series)

    def test_valid(self):
        sp = SparseSeries([0, 0, 0, nan, nan, 5, 6],
                          fill_value=0)

        sp_valid = sp.valid()
        assert_almost_equal(sp_valid, sp.to_dense().valid())
        self.assert_(sp_valid.index.equals(sp.to_dense().valid().index))
        self.assertEquals(len(sp_valid.sp_values), 2)

    def _check_all(self, check_func):
        check_func(self.bseries)
        check_func(self.iseries)
        check_func(self.zbseries)
        check_func(self.ziseries)

    def test_homogenize(self):
        def _check_matches(indices, expected):
            data = {}
            for i, idx in enumerate(indices):
                data[i] = SparseSeries(idx.to_int_index().indices,
                                       sparse_index=idx)
            homogenized = spm.homogenize(data)

            for k, v in homogenized.iteritems():
                assert(v.sp_index.equals(expected))

        indices1 = [BlockIndex(10, [2], [7]),
                   BlockIndex(10, [1, 6], [3, 4]),
                   BlockIndex(10, [0], [10])]
        expected1 = BlockIndex(10, [2, 6], [2, 3])
        _check_matches(indices1, expected1)

        indices2 = [BlockIndex(10, [2], [7]),
                   BlockIndex(10, [2], [7])]
        expected2 = indices2[0]
        _check_matches(indices2, expected2)

        # must have NaN fill value
        data = {'a' : SparseSeries(np.arange(7), sparse_index=expected2,
                                   fill_value=0)}
        nose.tools.assert_raises(Exception, spm.homogenize, data)

    def test_fill_value_corner(self):
        cop = self.zbseries.copy()
        cop.fill_value = 0
        result = self.bseries / cop

        self.assert_(np.isnan(result.fill_value))

        cop2 = self.zbseries.copy()
        cop2.fill_value = 1
        result = cop2 / cop
        self.assert_(np.isnan(result.fill_value))

    def test_shift(self):
        series = SparseSeries([nan, 1., 2., 3., nan, nan],
                              index=np.arange(6))

        shifted = series.shift(0)
        self.assert_(shifted is not series)
        assert_sp_series_equal(shifted, series)

        f = lambda s: s.shift(1)
        _dense_series_compare(series, f)

        f = lambda s: s.shift(-2)
        _dense_series_compare(series, f)

        series = SparseSeries([nan, 1., 2., 3., nan, nan],
                              index=DateRange('1/1/2000', periods=6))
        f = lambda s: s.shift(2, timeRule='WEEKDAY')
        _dense_series_compare(series, f)

        f = lambda s: s.shift(2, offset=datetools.bday)
        _dense_series_compare(series, f)

    def test_cumsum(self):
        result = self.bseries.cumsum()
        expected = self.bseries.to_dense().cumsum()
        self.assert_(isinstance(result, SparseSeries))
        assert_series_equal(result.to_dense(), expected)

class TestSparseTimeSeries(TestCase):
    pass

class TestSparseDataFrame(TestCase):
    klass = SparseDataFrame

    def setUp(self):
        self.data = {'A' : [nan, nan, nan, 0, 1, 2, 3, 4, 5, 6],
                     'B' : [0, 1, 2, nan, nan, nan, 3, 4, 5, 6],
                     'C' : np.arange(10),
                     'D' : [0, 1, 2, 3, 4, 5, nan, nan, nan, nan]}

        self.dates = DateRange('1/1/2011', periods=10)

        self.frame = SparseDataFrame(self.data, index=self.dates)
        self.iframe = SparseDataFrame(self.data, index=self.dates,
                                      default_kind='integer')

        values = self.frame.values.copy()
        values[np.isnan(values)] = 0

        self.zframe = SparseDataFrame(values, columns=['A', 'B', 'C', 'D'],
                                      default_fill_value=0,
                                      index=self.dates)

        values = self.frame.values.copy()
        values[np.isnan(values)] = 2
        self.fill_frame = SparseDataFrame(values, columns=['A', 'B', 'C', 'D'],
                                          default_fill_value=2,
                                          index=self.dates)

        self.empty = SparseDataFrame()

    def test_as_matrix(self):
        empty = self.empty.as_matrix()
        self.assert_(empty.shape == (0, 0))

        no_cols = SparseDataFrame(index=np.arange(10))
        mat = no_cols.as_matrix()
        self.assert_(mat.shape == (10, 0))

        no_index = SparseDataFrame(columns=np.arange(10))
        mat = no_index.as_matrix()
        self.assert_(mat.shape == (0, 10))

    def test_copy(self):
        cp = self.frame.copy()
        self.assert_(isinstance(cp, SparseDataFrame))
        assert_sp_frame_equal(cp, self.frame)
        self.assert_(cp.index is self.frame.index)

        # TODO: Test that DATA is copied!

    def test_constructor(self):
        for col, series in self.frame.iteritems():
            self.assert_(isinstance(series, SparseSeries))

        self.assert_(isinstance(self.iframe['A'].sp_index, IntIndex))

        # constructed zframe from matrix above
        self.assertEquals(self.zframe['A'].fill_value, 0)
        assert_almost_equal([0, 0, 0, 0, 1, 2, 3, 4, 5, 6],
                            self.zframe['A'].values)

        # construct from nested dict
        data = {}
        for c, s in self.frame.iteritems():
            data[c] = s.toDict()

        sdf = SparseDataFrame(data)
        assert_sp_frame_equal(sdf, self.frame)

        # TODO: test data is copied from inputs

        # init dict with different index
        idx = self.frame.index[:5]
        cons = SparseDataFrame(self.frame._series, index=idx,
                               columns=self.frame.columns,
                               default_fill_value=self.frame.default_fill_value,
                               default_kind=self.frame.default_kind)
        reindexed = self.frame.reindex(idx)
        assert_sp_frame_equal(cons, reindexed)

    def test_constructor_ndarray(self):
        # no index or columns
        sp = SparseDataFrame(self.frame.values)

        # 1d
        sp = SparseDataFrame(self.data['A'], index=self.dates,
                             columns=['A'])
        assert_sp_frame_equal(sp, self.frame.reindex(columns=['A']))

        # wrong length index / columns
        self.assertRaises(Exception, SparseDataFrame, self.frame.values,
                          index=self.frame.index[:-1])
        self.assertRaises(Exception, SparseDataFrame, self.frame.values,
                          columns=self.frame.columns[:-1])

    def test_constructor_empty(self):
        sp = SparseDataFrame()
        self.assert_(len(sp.index) == 0)
        self.assert_(len(sp.columns) == 0)

    def test_constructor_dataframe(self):
        dense = self.frame.to_dense()
        sp = SparseDataFrame(dense)
        assert_sp_frame_equal(sp, self.frame)

    def test_array_interface(self):
        res = np.sqrt(self.frame)
        dres = np.sqrt(self.frame.to_dense())
        assert_frame_equal(res.to_dense(), dres)

    def test_pickle(self):
        def _test_roundtrip(frame):
            pickled = pickle.dumps(frame, protocol=pickle.HIGHEST_PROTOCOL)
            unpickled = pickle.loads(pickled)
            assert_sp_frame_equal(frame, unpickled)

        self._check_all(_test_roundtrip)

    def test_dense_to_sparse(self):
        df = DataFrame({'A' : [nan, nan, nan, 1, 2],
                        'B' : [1, 2, nan, nan, nan]})
        sdf = df.to_sparse()
        self.assert_(isinstance(sdf, SparseDataFrame))
        self.assert_(np.isnan(sdf.default_fill_value))
        self.assert_(isinstance(sdf['A'].sp_index, BlockIndex))
        testing.assert_frame_equal(sdf.to_dense(), df)

        sdf = df.to_sparse(kind='integer')
        self.assert_(isinstance(sdf['A'].sp_index, IntIndex))

        df = DataFrame({'A' : [0, 0, 0, 1, 2],
                        'B' : [1, 2, 0, 0, 0]}, dtype=float)
        sdf = df.to_sparse(fill_value=0)
        self.assertEquals(sdf.default_fill_value, 0)
        testing.assert_frame_equal(sdf.to_dense(), df)

    def test_sparse_to_dense(self):
        pass

    def test_sparse_series_ops(self):
        self._check_all(self._check_frame_ops)

    def _check_frame_ops(self, frame):
        fill = frame.default_fill_value

        def _compare_to_dense(a, b, da, db, op):
            sparse_result = op(a, b)
            dense_result = op(da, db)

            dense_result = dense_result.to_sparse(fill_value=fill)
            assert_sp_frame_equal(sparse_result, dense_result,
                                  exact_indices=False)

            if isinstance(a, DataFrame) and isinstance(db, DataFrame):
                mixed_result = op(a, db)
                self.assert_(isinstance(mixed_result, SparseDataFrame))
                assert_sp_frame_equal(mixed_result, sparse_result,
                                      exact_indices=False)

        opnames = ['add', 'sub', 'mul', 'div']
        ops = [getattr(operator, name) for name in opnames]

        fidx = frame.index

        # time series operations

        series = [frame['A'], frame['B'],
                  frame['C'], frame['D'],
                  frame['A'].reindex(fidx[:7]),
                  frame['A'].reindex(fidx[::2]),
                  SparseSeries([], index=[])]

        for op in ops:
            _compare_to_dense(frame, frame[::2], frame.to_dense(),
                              frame[::2].to_dense(), op)
            for s in series:
                _compare_to_dense(frame, s, frame.to_dense(),
                                  s.to_dense(), op)
                _compare_to_dense(s, frame, s.to_dense(),
                                  frame.to_dense(), op)

        # cross-sectional operations
        series = [frame.xs(fidx[0]),
                  frame.xs(fidx[3]),
                  frame.xs(fidx[5]),
                  frame.xs(fidx[7]),
                  frame.xs(fidx[5])[:2]]

        for op in ops:
            for s in series:
                _compare_to_dense(frame, s, frame.to_dense(),
                                  s, op)
                _compare_to_dense(s, frame, s,
                                  frame.to_dense(), op)

    def test_op_corners(self):
        empty = self.empty + self.empty
        self.assert_(not empty)

        foo = self.frame + self.empty
        assert_sp_frame_equal(foo, self.frame * np.nan)

        foo = self.empty + self.frame
        assert_sp_frame_equal(foo, self.frame * np.nan)

    def test_scalar_ops(self):
        pass

    def test_getitem(self):
        pass

    def test_getitem_overload(self):
        # slicing
        sl = self.frame[:20]
        assert_sp_frame_equal(sl, self.frame.reindex(self.frame.index[:20]))

        # boolean indexing
        d = self.frame.index[5]
        indexer = self.frame.index > d

        subindex = self.frame.index[indexer]
        subframe = self.frame[indexer]

        self.assert_(np.array_equal(subindex, subframe.index))
        self.assertRaises(Exception, self.frame.__getitem__, indexer[:-1])

    def test_setitem(self):
        def _check_frame(frame):
            N = len(frame)

            # insert SparseSeries
            frame['E'] = frame['A']
            self.assert_(isinstance(frame['E'], SparseSeries))
            assert_sp_series_equal(frame['E'], frame['A'])

            # insert SparseSeries differently-indexed
            to_insert = frame['A'][::2]
            frame['E'] = to_insert
            assert_series_equal(frame['E'].to_dense(),
                                to_insert.to_dense().reindex(frame.index))

            # insert Series
            frame['F'] = frame['A'].to_dense()
            self.assert_(isinstance(frame['F'], SparseSeries))
            assert_sp_series_equal(frame['F'], frame['A'])

            # insert Series differently-indexed
            to_insert = frame['A'].to_dense()[::2]
            frame['G'] = to_insert
            assert_series_equal(frame['G'].to_dense(),
                                to_insert.reindex(frame.index))

            # insert ndarray
            frame['H'] = np.random.randn(N)
            self.assert_(isinstance(frame['H'], SparseSeries))

            to_sparsify = np.random.randn(N)
            to_sparsify[N // 2:] = frame.default_fill_value
            frame['I'] = to_sparsify
            self.assertEquals(len(frame['I'].sp_values), N // 2)

            # insert ndarray wrong size
            self.assertRaises(Exception, frame.__setitem__, 'foo',
                              np.random.randn(N - 1))

            # scalar value
            frame['J'] = 5
            self.assertEquals(len(frame['J'].sp_values), N)
            self.assert_((frame['J'].sp_values == 5).all())

            frame['K'] = frame.default_fill_value
            self.assertEquals(len(frame['K'].sp_values), 0)


        self._check_all(_check_frame)

    def test_setitem_corner(self):
        self.frame['a'] = self.frame['B']
        assert_sp_series_equal(self.frame['a'], self.frame['B'])

    def test_delitem(self):
        A = self.frame['A']
        C = self.frame['C']

        del self.frame['B']
        self.assert_('B' not in self.frame)
        assert_sp_series_equal(self.frame['A'], A)
        assert_sp_series_equal(self.frame['C'], C)

        del self.frame['D']
        self.assert_('D' not in self.frame)

        del self.frame['A']
        self.assert_('A' not in self.frame)

    def test_set_columns(self):
        self.frame.columns = self.frame.columns
        self.assertRaises(Exception, setattr, self.frame, 'columns',
                          self.frame.columns[:-1])

    def test_set_index(self):
        self.frame.index = self.frame.index
        self.assertRaises(Exception, setattr, self.frame, 'index',
                          self.frame.index[:-1])

    def test_append(self):
        a = self.frame[:5]
        b = self.frame[5:]

        appended = a.append(b)
        assert_sp_frame_equal(appended, self.frame)

    def test_apply(self):
        applied = self.frame.apply(np.sqrt)
        self.assert_(isinstance(applied, SparseDataFrame))
        assert_almost_equal(applied.values, np.sqrt(self.frame.values))

        applied = self.fill_frame.apply(np.sqrt)
        self.assert_(applied['A'].fill_value == np.sqrt(2))

        # agg / broadcast
        applied = self.frame.apply(np.sum)
        assert_series_equal(applied,
                            self.frame.to_dense().apply(np.sum))

        broadcasted = self.frame.apply(np.sum, broadcast=True)
        self.assert_(isinstance(broadcasted, SparseDataFrame))
        assert_frame_equal(broadcasted.to_dense(),
                           self.frame.to_dense().apply(np.sum, broadcast=True))

        self.assert_(self.empty.apply(np.sqrt) is self.empty)

    def test_applymap(self):
        # just test that it works
        result = self.frame.applymap(lambda x: x * 2)
        self.assert_(isinstance(result, SparseDataFrame))

    def test_astype(self):
        pass

    def test_fillna(self):
        self.assertRaises(NotImplementedError, self.frame.fillna, 0)

    def test_rename(self):
        # just check this works
        renamed = self.frame.rename(index=str)
        renamed = self.frame.rename(columns=lambda x: '%s%d' % (x, len(x)))

    def test_corr(self):
        res = self.frame.corr()
        assert_frame_equal(res, self.frame.to_dense().corr())

    def test_describe(self):
        self.frame['foo'] = np.nan
        desc = self.frame.describe()

    def test_join(self):
        left = self.frame.ix[:, ['A', 'B']]
        right = self.frame.ix[:, ['C', 'D']]
        joined = left.join(right)
        assert_sp_frame_equal(joined, self.frame)

        right = self.frame.ix[:, ['B', 'D']]
        self.assertRaises(Exception, left.join, right)

    def test_reindex(self):

        def _check_frame(frame):
            index = frame.index
            sidx = index[::2]
            sidx2 = index[:5]

            sparse_result = frame.reindex(sidx)
            dense_result = frame.to_dense().reindex(sidx)
            assert_frame_equal(sparse_result.to_dense(), dense_result)

            assert_frame_equal(frame.reindex(list(sidx)).to_dense(),
                               dense_result)

            sparse_result2 = sparse_result.reindex(index)
            dense_result2 = dense_result.reindex(index)
            assert_frame_equal(sparse_result2.to_dense(), dense_result2)

            # propagate CORRECT fill value
            assert_almost_equal(sparse_result.default_fill_value,
                                frame.default_fill_value)
            assert_almost_equal(sparse_result['A'].fill_value,
                                frame['A'].fill_value)

            # length zero
            length_zero = frame.reindex([])
            self.assertEquals(len(length_zero), 0)
            self.assertEquals(len(length_zero.columns), len(frame.columns))
            self.assertEquals(len(length_zero['A']), 0)

            # frame being reindexed has length zero
            length_n = length_zero.reindex(index)
            self.assertEquals(len(length_n), len(frame))
            self.assertEquals(len(length_n.columns), len(frame.columns))
            self.assertEquals(len(length_n['A']), len(frame))

            # reindex columns
            reindexed = frame.reindex(columns=['A', 'B', 'Z'])
            self.assertEquals(len(reindexed.columns), 3)
            assert_almost_equal(reindexed['Z'].fill_value,
                                frame.default_fill_value)
            self.assert_(np.isnan(reindexed['Z'].sp_values).all())

        _check_frame(self.frame)
        _check_frame(self.iframe)
        _check_frame(self.zframe)
        _check_frame(self.fill_frame)

    def test_fillna(self):
        pass

    def test_density(self):
        df = SparseDataFrame({'A' : [nan, nan, nan, 0, 1, 2, 3, 4, 5, 6],
                              'B' : [0, 1, 2, nan, nan, nan, 3, 4, 5, 6],
                              'C' : np.arange(10),
                              'D' : [0, 1, 2, 3, 4, 5, nan, nan, nan, nan]})

        self.assertEquals(df.density, 0.75)

    def test_to_dense(self):
        def _check(frame):
            dense_dm = frame.to_dense()
            assert_frame_equal(frame, dense_dm)

        self._check_all(_check)

    def test_stack_sparse_frame(self):
        def _check(frame):
            dense_frame = frame.to_dense()

            wp = WidePanel.from_dict({'foo' : frame})
            from_dense_lp = wp.to_long()

            from_sparse_lp = spm.stack_sparse_frame(frame)

            self.assert_(np.array_equal(from_dense_lp.values,
                                        from_sparse_lp.values))


        _check(self.frame)
        _check(self.iframe)

        # for now
        self.assertRaises(Exception, _check, self.zframe)
        self.assertRaises(Exception, _check, self.fill_frame)

    def test_transpose(self):
        def _check(frame):
            transposed = frame.T
            untransposed = transposed.T
            assert_sp_frame_equal(frame, untransposed)
        self._check_all(_check)

    def test_shift(self):
        def _check(frame):
            shifted = frame.shift(0)
            self.assert_(shifted is not frame)
            assert_sp_frame_equal(shifted, frame)

            f = lambda s: s.shift(1)
            _dense_frame_compare(frame, f)

            f = lambda s: s.shift(-2)
            _dense_frame_compare(frame, f)

            f = lambda s: s.shift(2, timeRule='WEEKDAY')
            _dense_frame_compare(frame, f)

            f = lambda s: s.shift(2, offset=datetools.bday)
            _dense_frame_compare(frame, f)

        self._check_all(_check)

    def test_count(self):
        result = self.frame.count()
        dense_result = self.frame.to_dense().count()
        assert_series_equal(result, dense_result)

        result = self.frame.count(1)
        dense_result = self.frame.to_dense().count(1)
        assert_series_equal(result, dense_result)

    def test_cumsum(self):
        result = self.frame.cumsum()
        expected = self.frame.to_dense().cumsum()
        self.assert_(isinstance(result, SparseDataFrame))
        assert_frame_equal(result.to_dense(), expected)

    def _check_all(self, check_func):
        check_func(self.frame)
        check_func(self.iframe)
        check_func(self.zframe)
        check_func(self.fill_frame)

def _dense_series_compare(s, f):
    result = f(s)
    assert(isinstance(result, SparseSeries))
    dense_result = f(s.to_dense())
    assert_series_equal(result.to_dense(), dense_result)

def _dense_frame_compare(frame, f):
    result = f(frame)
    assert(isinstance(frame, SparseDataFrame))
    dense_result = f(frame.to_dense())
    assert_frame_equal(result.to_dense(), dense_result)

def panel_data1():
    index = DateRange('1/1/2011', periods=8)

    return DataFrame({
        'A' : [nan, nan, nan, 0, 1, 2, 3, 4],
        'B' : [0, 1, 2, 3, 4, nan, nan, nan],
        'C' : [0, 1, 2, nan, nan, nan, 3, 4],
        'D' : [nan, 0, 1, nan, 2, 3, 4, nan]
        }, index=index)


def panel_data2():
    index = DateRange('1/1/2011', periods=9)

    return DataFrame({
        'A' : [nan, nan, nan, 0, 1, 2, 3, 4, 5],
        'B' : [0, 1, 2, 3, 4, 5, nan, nan, nan],
        'C' : [0, 1, 2, nan, nan, nan, 3, 4, 5],
        'D' : [nan, 0, 1, nan, 2, 3, 4, 5, nan]
        }, index=index)


def panel_data3():
    index = DateRange('1/1/2011', periods=10).shift(-2)

    return DataFrame({
        'A' : [nan, nan, nan, 0, 1, 2, 3, 4, 5, 6],
        'B' : [0, 1, 2, 3, 4, 5, 6, nan, nan, nan],
        'C' : [0, 1, 2, nan, nan, nan, 3, 4, 5, 6],
        'D' : [nan, 0, 1, nan, 2, 3, 4, 5, 6, nan]
        }, index=index)

class TestSparseWidePanel(TestCase,
                          test_panel.SafeForLongAndSparse,
                          test_panel.SafeForSparse):

    @staticmethod
    def assert_panel_equal(x, y):
        assert_sp_panel_equal(x, y)

    def setUp(self):
        self.data_dict = {
            'ItemA' : panel_data1(),
            'ItemB' : panel_data2(),
            'ItemC' : panel_data3(),
            'ItemD' : panel_data1(),
        }
        self.panel = SparseWidePanel(self.data_dict)

    @staticmethod
    def _test_op(panel, op):
        # arithmetic tests
        result = op(panel, 1)
        assert_sp_frame_equal(result['ItemA'], op(panel['ItemA'], 1))

    def test_constructor(self):
        self.assertRaises(Exception, SparseWidePanel, self.data_dict,
                          items=['Item0', 'ItemA', 'ItemB'])

    def test_from_dict(self):
        fd = SparseWidePanel.from_dict(self.data_dict)
        assert_sp_panel_equal(fd, self.panel)

    def test_pickle(self):
        def _test_roundtrip(panel):
            pickled = pickle.dumps(panel, protocol=pickle.HIGHEST_PROTOCOL)
            unpickled = pickle.loads(pickled)
            assert_sp_panel_equal(panel, unpickled)

        _test_roundtrip(self.panel)

    def test_dense_to_sparse(self):
        wp = WidePanel.from_dict(self.data_dict)
        dwp = wp.to_sparse()
        self.assert_(isinstance(dwp['ItemA']['A'], SparseSeries))

    def test_to_dense(self):
        dwp = self.panel.to_dense()
        dwp2 = WidePanel.from_dict(self.data_dict)
        assert_panel_equal(dwp, dwp2)

    def test_to_long(self):
        def _compare_with_dense(panel):
            slp = panel.to_long()
            dlp = panel.to_dense().to_long()

            self.assert_(np.array_equal(slp.values, dlp.values))
            self.assert_(np.array_equal(slp.major_labels,
                                        dlp.major_labels))
            self.assert_(np.array_equal(slp.minor_labels,
                                        dlp.minor_labels))

        _compare_with_dense(self.panel)
        _compare_with_dense(self.panel.reindex(items=['ItemA']))

        zero_panel = SparseWidePanel(self.data_dict, default_fill_value=0)
        self.assertRaises(Exception, zero_panel.to_long)

        self.assertRaises(Exception, self.panel.to_long,
                          filter_observations=False)

    def test_long_to_wide_sparse(self):
        pass

    def test_values(self):
        pass

    def test_setitem(self):
        self.panel['ItemE'] = self.panel['ItemC']
        self.panel['ItemF'] = self.panel['ItemC'].to_dense()

        assert_sp_frame_equal(self.panel['ItemE'], self.panel['ItemC'])
        assert_sp_frame_equal(self.panel['ItemF'], self.panel['ItemC'])
        assert_almost_equal(self.panel.items, ['ItemA', 'ItemB', 'ItemC',
                                               'ItemD', 'ItemE', 'ItemF'])

        self.assertRaises(Exception, self.panel.__setitem__, 'item6', 1)

    def test_delitem_pop(self):
        del self.panel['ItemB']
        assert_almost_equal(self.panel.items, ['ItemA', 'ItemC', 'ItemD'])
        crackle = self.panel['ItemC']
        pop = self.panel.pop('ItemC')
        self.assert_(pop is crackle)
        assert_almost_equal(self.panel.items, ['ItemA', 'ItemD'])

        self.assertRaises(KeyError, self.panel.__delitem__, 'ItemC')

    def test_copy(self):
        cop = self.panel.copy()
        assert_sp_panel_equal(cop, self.panel)

    def test_reindex(self):
        def _compare_with_dense(swp, items, major, minor):
            swp_re = swp.reindex(items=items, major=major,
                                 minor=minor)
            dwp_re = swp.to_dense().reindex(items=items, major=major,
                                            minor=minor)
            assert_panel_equal(swp_re.to_dense(), dwp_re)

        _compare_with_dense(self.panel, self.panel.items[:2],
                            self.panel.major_axis[::2],
                            self.panel.minor_axis[::2])
        _compare_with_dense(self.panel, None,
                            self.panel.major_axis[::2],
                            self.panel.minor_axis[::2])

        self.assertRaises(ValueError, self.panel.reindex)

        # TODO: do something about this later...
        self.assertRaises(Exception, self.panel.reindex,
                          items=['item0', 'ItemA', 'ItemB'])

    def test_operators(self):
        def _check_ops(panel):
            def _dense_comp(op):
                dense = panel.to_dense()
                sparse_result = op(panel)
                dense_result = op(dense)
                assert_panel_equal(sparse_result.to_dense(), dense_result)

            op1 = lambda x: x + 2

            _dense_comp(op1)
            op2 = lambda x: x.add(x.reindex(major=x.major_axis[::2]))
            _dense_comp(op2)
            op3 = lambda x: x.subtract(x.mean(0), axis=0)
            _dense_comp(op3)
            op4 = lambda x: x.subtract(x.mean(1), axis=1)
            _dense_comp(op4)
            op5 = lambda x: x.subtract(x.mean(2), axis=2)
            _dense_comp(op5)

            # TODO: this case not yet supported!
            # op6 = lambda x: x.add(x.to_long())
            # _dense_comp(op6)

        _check_ops(self.panel)

    def test_major_xs(self):
        def _dense_comp(sparse):
            dense = sparse.to_dense()

            for idx in sparse.major_axis:
                dslice = dense.major_xs(idx)
                sslice = sparse.major_xs(idx)
                assert_frame_equal(dslice, sslice)

        _dense_comp(self.panel)

    def test_minor_xs(self):
        def _dense_comp(sparse):
            dense = sparse.to_dense()

            for idx in sparse.minor_axis:
                dslice = dense.minor_xs(idx)
                sslice = sparse.minor_xs(idx).to_dense()
                assert_frame_equal(dslice, sslice)

        _dense_comp(self.panel)

if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

    # nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure',
    #                      '--with-profile'],
    #                exit=False)
