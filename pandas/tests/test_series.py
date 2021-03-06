# pylint: disable-msg=E1101,W0612

from datetime import datetime, timedelta
import os
import operator
import unittest

from numpy import nan
import numpy as np

from pandas import Index, Series, TimeSeries, DataFrame, isnull
from pandas.core.index import MultiIndex
import pandas.core.datetools as datetools
from pandas.util.testing import assert_series_equal, assert_almost_equal
import pandas.util.testing as common

#-------------------------------------------------------------------------------
# Series test cases

class TestSeries(unittest.TestCase):

    def setUp(self):
        self.ts = common.makeTimeSeries()
        self.series = common.makeStringSeries()
        self.objSeries = common.makeObjectSeries()

        self.empty = Series([], index=[])

    def test_constructor(self):
        # Recognize TimeSeries
        self.assert_(isinstance(self.ts, TimeSeries))

        # Pass in Series
        derived = Series(self.ts)
        self.assert_(isinstance(derived, TimeSeries))

        self.assert_(common.equalContents(derived.index, self.ts.index))
        # Ensure new index is not created
        self.assertEquals(id(self.ts.index), id(derived.index))

        # Pass in scalar
        scalar = Series(0.5)
        self.assert_(isinstance(scalar, float))

        # Mixed type Series
        mixed = Series(['hello', np.NaN], index=[0, 1])
        self.assert_(mixed.dtype == np.object_)
        self.assert_(mixed[1] is np.NaN)

        self.assert_(not isinstance(self.empty, TimeSeries))
        self.assert_(not isinstance(Series({}), TimeSeries))

        self.assertRaises(Exception, Series, np.random.randn(3, 3),
                          index=np.arange(3))

    def test_constructor_default_index(self):
        s = Series([0, 1, 2])
        assert_almost_equal(s.index, np.arange(3))

    def test_constructor_corner(self):
        df = common.makeTimeDataFrame()
        objs = [df, df]
        s = Series(objs, index=[0, 1])
        self.assert_(isinstance(s, Series))

    def test_fromDict(self):
        data = {'a' : 0, 'b' : 1, 'c' : 2, 'd' : 3}

        series = Series(data)
        self.assert_(common.is_sorted(series.index))

        data = {'a' : 0, 'b' : '1', 'c' : '2', 'd' : datetime.now()}
        series = Series(data)
        self.assert_(series.dtype == np.object_)

        data = {'a' : 0, 'b' : '1', 'c' : '2', 'd' : '3'}
        series = Series(data)
        self.assert_(series.dtype == np.object_)

        data = {'a' : '0', 'b' : '1'}
        series = Series(data, dtype=float)
        self.assert_(series.dtype == np.float64)

    def test_setindex(self):
        # wrong type
        series = self.series.copy()
        self.assertRaises(TypeError, series._set_index, None)

        # wrong length
        series = self.series.copy()
        self.assertRaises(AssertionError, series._set_index,
                          np.arange(len(series) - 1))

        # works
        series = self.series.copy()
        series.index = np.arange(len(series))
        self.assert_(isinstance(series.index, Index))

    def test_array_finalize(self):
        pass

    def test_fromValue(self):
        nans = Series(np.NaN, index=self.ts.index)
        self.assert_(nans.dtype == np.float_)
        self.assertEqual(len(nans), len(self.ts))

        strings = Series('foo', index=self.ts.index)
        self.assert_(strings.dtype == np.object_)
        self.assertEqual(len(strings), len(self.ts))

        d = datetime.now()
        dates = Series(d, index=self.ts.index)
        self.assert_(dates.dtype == np.object_)
        self.assertEqual(len(dates), len(self.ts))

    def test_contains(self):
        common.assert_contains_all(self.ts.index, self.ts)

    def test_save_load(self):
        self.series.save('tmp1')
        self.ts.save('tmp3')
        unp_series = Series.load('tmp1')
        unp_ts = Series.load('tmp3')
        os.remove('tmp1')
        os.remove('tmp3')
        assert_series_equal(unp_series, self.series)
        assert_series_equal(unp_ts, self.ts)

    def test_getitem_get(self):
        idx1 = self.series.index[5]
        idx2 = self.objSeries.index[5]

        self.assertEqual(self.series[idx1], self.series.get(idx1))
        self.assertEqual(self.objSeries[idx2], self.objSeries.get(idx2))

        self.assertEqual(self.series[idx1], self.series[5])
        self.assertEqual(self.objSeries[idx2], self.objSeries[5])

        self.assert_(self.series.get(-1) is None)
        self.assertEqual(self.series[5], self.series.get(self.series.index[5]))

        # missing
        d = self.ts.index[0] - datetools.bday
        self.assertRaises(KeyError, self.ts.__getitem__, d)

    def test_getitem_regression(self):
        s = Series(range(5), index=range(5))
        result = s[range(5)]
        assert_series_equal(result, s)

    def test_getitem_int64(self):
        idx = np.int64(5)
        self.assertEqual(self.ts[idx], self.ts[5])

    def test_getitem_fancy(self):
        slice1 = self.series[[1,2,3]]
        slice2 = self.objSeries[[1,2,3]]
        self.assertEqual(self.series.index[2], slice1.index[1])
        self.assertEqual(self.objSeries.index[2], slice2.index[1])
        self.assertEqual(self.series[2], slice1[1])
        self.assertEqual(self.objSeries[2], slice2[1])

    def test_getitem_boolean(self):
        s = self.series
        mask = s > s.median()

        # passing list is OK
        result = s[list(mask)]
        expected = s[mask]
        assert_series_equal(result, expected)
        self.assert_(np.array_equal(result.index, s.index[mask]))

    def test_getitem_boolean_object(self):
        # using column from DataFrame
        s = self.series
        mask = s > s.median()
        omask = mask.astype(object)

        # getitem
        result = s[omask]
        expected = s[mask]
        assert_series_equal(result, expected)

        # setitem
        cop = s.copy()
        cop[omask] = 5
        s[mask] = 5
        assert_series_equal(cop, s)

        # nans raise exception
        omask[5:10] = np.nan
        self.assertRaises(Exception, s.__getitem__, omask)
        self.assertRaises(Exception, s.__setitem__, omask, 5)

    def test_getitem_setitem_boolean_corner(self):
        ts = self.ts
        mask_shifted = ts.shift(1, offset=datetools.bday) > ts.median()
        self.assertRaises(Exception, ts.__getitem__, mask_shifted)
        self.assertRaises(Exception, ts.__setitem__, mask_shifted, 1)

        self.assertRaises(Exception, ts.ix.__getitem__, mask_shifted)
        self.assertRaises(Exception, ts.ix.__setitem__, mask_shifted, 1)

    def test_slice(self):
        numSlice = self.series[10:20]
        numSliceEnd = self.series[-10:]
        objSlice = self.objSeries[10:20]

        self.assert_(self.series.index[9] not in numSlice.index)
        self.assert_(self.objSeries.index[9] not in objSlice.index)

        self.assertEqual(len(numSlice), len(numSlice.index))
        self.assertEqual(self.series[numSlice.index[0]],
                         numSlice[numSlice.index[0]])

        self.assertEqual(numSlice.index[1], self.series.index[11])

        self.assert_(common.equalContents(numSliceEnd,
                                          np.array(self.series)[-10:]))

    def test_setitem(self):
        self.ts[self.ts.index[5]] = np.NaN
        self.ts[[1,2,17]] = np.NaN
        self.ts[6] = np.NaN
        self.assert_(np.isnan(self.ts[6]))
        self.assert_(np.isnan(self.ts[2]))
        self.ts[np.isnan(self.ts)] = 5
        self.assert_(not np.isnan(self.ts[2]))

        # caught this bug when writing tests
        series = Series(common.makeIntIndex(20).astype(float),
                        index=common.makeIntIndex(20))

        series[::2] = 0
        self.assert_((series[::2] == 0).all())

        # set item that's not contained
        self.assertRaises(Exception, self.series.__setitem__,
                          'foobar', 1)

    def test_setslice(self):
        sl = self.ts[5:20]
        self.assertEqual(len(sl), len(sl.index))
        self.assertEqual(len(sl.index.indexMap), len(sl.index))

    def test_ix_getitem(self):
        inds = self.series.index[[3,4,7]]
        assert_series_equal(self.series.ix[inds], self.series.reindex(inds))
        assert_series_equal(self.series.ix[5::2], self.series[5::2])

        # slice with indices
        d1, d2 = self.series.index[[5, 15]]
        result = self.series.ix[d1:d2]
        expected = self.series.truncate(d1, d2)
        assert_series_equal(result, expected)

        # boolean
        mask = self.series > self.series.median()
        assert_series_equal(self.series.ix[mask], self.series[mask])

        # ask for index value
        self.assertEquals(self.series.ix[d1], self.series[d1])
        self.assertEquals(self.series.ix[d2], self.series[d2])

    def test_ix_getitem_iterator(self):
        idx = iter(self.series.index[:10])
        result = self.series.ix[idx]
        assert_series_equal(result, self.series[:10])

    def test_ix_setitem(self):
        inds = self.series.index[[3,4,7]]

        result = self.series.copy()
        result.ix[inds] = 5

        expected = self.series.copy()
        expected[[3,4,7]] = 5
        assert_series_equal(result, expected)

        result.ix[5:10] = 10
        expected[5:10] = 10
        assert_series_equal(result, expected)

        # set slice with indices
        d1, d2 = self.series.index[[5, 15]]
        result.ix[d1:d2] = 6
        expected[5:16] = 6 # because it's inclusive
        assert_series_equal(result, expected)

        # set index value
        self.series.ix[d1] = 4
        self.series.ix[d2] = 6
        self.assertEquals(self.series[d1], 4)
        self.assertEquals(self.series[d2], 6)

    def test_ix_setitem_boolean(self):
        mask = self.series > self.series.median()

        result = self.series.copy()
        result.ix[mask] = 0
        expected = self.series
        expected[mask] = 0
        assert_series_equal(result, expected)

    def test_ix_setitem_corner(self):
        inds = list(self.series.index[[5, 8, 12]])
        self.series.ix[inds] = 5
        self.assertRaises(Exception, self.series.ix.__setitem__,
                          inds + ['foo'], 5)

    def test_repr(self):
        str(self.ts)
        str(self.series)
        str(self.series.astype(int))
        str(self.objSeries)

        str(Series(common.randn(1000), index=np.arange(1000)))

        # empty
        str(self.empty)

        # with NaNs
        self.series[5:7] = np.NaN
        str(self.series)

    def test_toString(self):
        from cStringIO import StringIO
        self.ts.toString(buffer=StringIO())

    def test_iter(self):
        for i, val in enumerate(self.series):
            self.assertEqual(val, self.series[i])

        for i, val in enumerate(self.ts):
            self.assertEqual(val, self.ts[i])

    def test_keys(self):
        self.assert_(self.ts.keys() is self.ts.index)

    def test_values(self):
        self.assert_(np.array_equal(self.ts, self.ts.values))

    def test_iteritems(self):
        for idx, val in self.series.iteritems():
            self.assertEqual(val, self.series[idx])

        for idx, val in self.ts.iteritems():
            self.assertEqual(val, self.ts[idx])

    def test_stats(self):
        self.series[5:15] = np.NaN

        s1 = np.array(self.series)
        s1 = s1[-np.isnan(s1)]

        self.assertEquals(np.min(s1), self.series.min())
        self.assertEquals(np.max(s1), self.series.max())
        self.assertEquals(np.sum(s1), self.series.sum())
        self.assertEquals(np.mean(s1), self.series.mean())
        self.assertEquals(np.std(s1, ddof=1), self.series.std())
        self.assertEquals(np.var(s1, ddof=1), self.series.var())

        try:
            from scipy.stats import skew
            common.assert_almost_equal(skew(s1, bias=False),
                                       self.series.skew())
        except ImportError:
            pass

        self.assert_(not np.isnan(np.sum(self.series)))
        self.assert_(not np.isnan(np.mean(self.series)))
        self.assert_(not np.isnan(np.std(self.series)))
        self.assert_(not np.isnan(np.var(self.series)))
        self.assert_(not np.isnan(np.min(self.series)))
        self.assert_(not np.isnan(np.max(self.series)))

        self.assert_(np.isnan(Series([1.], index=[1]).std()))
        self.assert_(np.isnan(Series([1.], index=[1]).var()))
        self.assert_(np.isnan(Series([1.], index=[1]).skew()))

        # all NA
        allna = self.series * nan
        self.assert_(np.isnan(allna.sum()))
        self.assert_(np.isnan(allna.mean()))
        self.assert_(np.isnan(allna.std()))
        self.assert_(np.isnan(allna.skew()))

    def test_quantile(self):
        from scipy.stats import scoreatpercentile

        q = self.ts.quantile(0.1)
        self.assertEqual(q, scoreatpercentile(self.ts.valid(), 10))

        q = self.ts.quantile(0.9)
        self.assertEqual(q, scoreatpercentile(self.ts.valid(), 90))

    def test_describe(self):
        _ = self.series.describe()
        _ = self.ts.describe()

    def test_append(self):
        appendedSeries = self.series.append(self.ts)
        for idx, value in appendedSeries.iteritems():
            if idx in self.series.index:
                self.assertEqual(value, self.series[idx])
            elif idx in self.ts.index:
                self.assertEqual(value, self.ts[idx])
            else:
                self.fail("orphaned index!")

        self.assertRaises(Exception, self.ts.append, self.ts)

    def test_operators(self):
        series = self.ts
        other = self.ts[::2]

        def _check_op(other, op):
            cython_or_numpy = op(series, other)
            python = series.combine(other, op)

            common.assert_almost_equal(cython_or_numpy, python)

        def check(other):
            _check_op(other, operator.add)
            _check_op(other, operator.sub)
            _check_op(other, operator.div)
            _check_op(other, operator.mul)
            _check_op(other, operator.pow)

            _check_op(other, lambda x, y: operator.add(y, x))
            _check_op(other, lambda x, y: operator.sub(y, x))
            _check_op(other, lambda x, y: operator.div(y, x))
            _check_op(other, lambda x, y: operator.mul(y, x))
            _check_op(other, lambda x, y: operator.pow(y, x))

        check(self.ts * 2)
        check(self.ts[::2])
        check(5)

        def check_comparators(other):
            _check_op(other, operator.gt)
            _check_op(other, operator.ge)
            _check_op(other, operator.eq)
            _check_op(other, operator.lt)
            _check_op(other, operator.le)

        check_comparators(5)
        check_comparators(self.ts + 1)

    def test_operators_date(self):
        result = self.objSeries + timedelta(1)
        result = self.objSeries - timedelta(1)

    def test_operators_corner(self):
        series = self.ts

        empty = Series([], index=Index([]))

        result = series + empty
        self.assert_(np.isnan(result).all())

        result = empty + Series([], index=Index([]))
        self.assert_(len(result) == 0)

        # TODO: this returned NotImplemented earlier, what to do?
        # deltas = Series([timedelta(1)] * 5, index=np.arange(5))
        # sub_deltas = deltas[::2]
        # deltas5 = deltas * 5
        # deltas = deltas + sub_deltas

        # float + int
        int_ts = self.ts.astype(int)[:-5]
        added = self.ts + int_ts
        expected = self.ts.values[:-5] + int_ts.values
        self.assert_(np.array_equal(added[:-5], expected))

    def test_operators_reverse_object(self):
        # GH 56
        arr = Series(np.random.randn(10), index=np.arange(10),
                     dtype=object)

        def _check_op(arr, op):
            result = op(1., arr)
            expected = op(1., arr.astype(float))
            assert_series_equal(result.astype(float), expected)

        _check_op(arr, operator.add)
        _check_op(arr, operator.sub)
        _check_op(arr, operator.mul)
        _check_op(arr, operator.div)

    def test_operators_frame(self):
        # rpow does not work with DataFrame
        df = DataFrame({'A' : self.ts})

        common.assert_almost_equal(self.ts + self.ts, (self.ts + df)['A'])
        common.assert_almost_equal(self.ts ** self.ts, (self.ts ** df)['A'])

    def test_operators_combine(self):
        def _check_fill(meth, op, a, b, fill_value=0):
            exp_index = a.index.union(b.index)
            a = a.reindex(exp_index)
            b = b.reindex(exp_index)

            amask = isnull(a)
            bmask = isnull(b)

            exp_values = []
            for i in range(len(exp_index)):
                if amask[i]:
                    if bmask[i]:
                        exp_values.append(nan)
                        continue
                    exp_values.append(op(fill_value, b[i]))
                elif bmask[i]:
                    if amask[i]:
                        exp_values.append(nan)
                        continue
                    exp_values.append(op(a[i], fill_value))
                else:
                    exp_values.append(op(a[i], b[i]))

            result = meth(a, b, fill_value=fill_value)
            expected = Series(exp_values, exp_index)
            assert_series_equal(result, expected)

        a = Series([nan, 1., 2., 3., nan], index=np.arange(5))
        b = Series([nan, 1, nan, 3, nan, 4.], index=np.arange(6))

        ops = [Series.add, Series.sub, Series.mul, Series.div]
        equivs = [operator.add, operator.sub, operator.mul, operator.div]
        fillvals = [0, 0, 1, 1]

        for op, equiv_op, fv in zip(ops, equivs, fillvals):
            result = op(a, b)
            exp = equiv_op(a, b)
            assert_series_equal(result, exp)
            _check_fill(op, equiv_op, a, b, fill_value=fv)

    def test_combineFirst(self):
        series = Series(common.makeIntIndex(20).astype(float),
                        index=common.makeIntIndex(20))

        series_copy = series * 2
        series_copy[::2] = np.NaN

        # nothing used from the input
        combined = series.combineFirst(series_copy)

        self.assert_(np.array_equal(combined, series))

        # Holes filled from input
        combined = series_copy.combineFirst(series)
        self.assert_(np.isfinite(combined).all())

        self.assert_(np.array_equal(combined[::2], series[::2]))
        self.assert_(np.array_equal(combined[1::2], series_copy[1::2]))

        # mixed types
        index = common.makeStringIndex(20)
        floats = Series(common.randn(20), index=index)
        strings = Series(common.makeStringIndex(10), index=index[::2])

        combined = strings.combineFirst(floats)

        common.assert_dict_equal(strings, combined, compare_keys=False)
        common.assert_dict_equal(floats[1::2], combined, compare_keys=False)

        # corner case
        s = Series([1., 2, 3], index=[0, 1, 2])
        result = s.combineFirst(Series([], index=[]))
        assert_series_equal(s, result)

    def test_overloads(self):
        methods = ['argsort', 'cumsum', 'cumprod']

        for method in methods:
            func = getattr(np, method)

            self.assert_(np.array_equal(func(self.ts), func(np.array(self.ts))))

            # with missing values
            ts = self.ts.copy()
            ts[::2] = np.NaN

            result = func(ts)[1::2]
            expected = func(np.array(ts.valid()))

            self.assert_(np.array_equal(result, expected))

        argsorted = self.ts.argsort()
        self.assert_(issubclass(argsorted.dtype.type, np.integer))

    def test_median(self):
        self.assertAlmostEqual(np.median(self.ts), self.ts.median())

        ts = self.ts.copy()
        ts[::2] = np.NaN

        self.assertAlmostEqual(np.median(ts.valid()), ts.median())

        # test with integers, test failure
        int_ts = TimeSeries(np.ones(10, dtype=int), index=range(10))
        self.assertAlmostEqual(np.median(int_ts), int_ts.median())

    def test_corr(self):
        # full overlap
        self.assertAlmostEqual(self.ts.corr(self.ts), 1)

        # partial overlap
        self.assertAlmostEqual(self.ts[:15].corr(self.ts[5:]), 1)

        # No overlap
        self.assert_(np.isnan(self.ts[::2].corr(self.ts[1::2])))

        # additional checks?

    def test_copy(self):
        ts = self.ts.copy()

        ts[::2] = np.NaN

        # Did not modify original Series
        self.assertFalse(np.isnan(self.ts[0]))

    def test_count(self):
        self.assertEqual(self.ts.count(), len(self.ts))

        self.ts[::2] = np.NaN

        self.assertEqual(self.ts.count(), np.isfinite(self.ts).sum())

    def test_sort(self):
        ts = self.ts.copy()
        ts.sort()

        self.assert_(np.array_equal(ts, self.ts.order()))
        self.assert_(np.array_equal(ts.index, self.ts.order().index))

    def test_order(self):
        ts = self.ts.copy()
        ts[:5] = np.NaN
        vals = ts.values

        result = ts.order()
        self.assert_(np.isnan(result[-5:]).all())
        self.assert_(np.array_equal(result[:-5], np.sort(vals[5:])))

        result = ts.order(na_last=False)
        self.assert_(np.isnan(result[:5]).all())
        self.assert_(np.array_equal(result[5:], np.sort(vals[5:])))

        # something object-type
        ser = Series(['A', 'B'], [1, 2])
        # no failure
        ser.order()

        # ascending=False
        ordered = ts.order(ascending=False)
        expected = np.sort(ts.valid().values)[::-1]
        assert_almost_equal(expected, ordered.valid().values)
        ordered = ts.order(ascending=False, na_last=False)
        assert_almost_equal(expected, ordered.valid().values)

    def test_map(self):
        result = self.ts.map(lambda x: x * 2)

        self.assert_(np.array_equal(result, self.ts * 2))

    def test_toCSV(self):
        self.ts.toCSV('_foo')
        os.remove('_foo')

    def test_toDict(self):
        self.assert_(np.array_equal(Series(self.ts.toDict()), self.ts))

    def test_clip(self):
        val = self.ts.median()

        self.assertEqual(self.ts.clip_lower(val).min(), val)
        self.assertEqual(self.ts.clip_upper(val).max(), val)

        self.assertEqual(self.ts.clip(lower=val).min(), val)
        self.assertEqual(self.ts.clip(upper=val).max(), val)

    def test_valid(self):
        ts = self.ts.copy()
        ts[::2] = np.NaN

        result = ts.valid()
        self.assertEqual(len(result), ts.count())

        common.assert_dict_equal(result, ts, compare_keys=False)

    def test_shift(self):
        shifted = self.ts.shift(1)
        unshifted = shifted.shift(-1)

        common.assert_dict_equal(unshifted.valid(), self.ts, compare_keys=False)

        offset = datetools.bday
        shifted = self.ts.shift(1, offset=offset)
        unshifted = shifted.shift(-1, offset=offset)

        assert_series_equal(unshifted, self.ts)

        unshifted = self.ts.shift(0, offset=offset)
        assert_series_equal(unshifted, self.ts)

        shifted = self.ts.shift(1, timeRule='WEEKDAY')
        unshifted = shifted.shift(-1, timeRule='WEEKDAY')

        assert_series_equal(unshifted, self.ts)

        # corner case
        unshifted = self.ts.shift(0)
        assert_series_equal(unshifted, self.ts)

    def test_truncate(self):
        offset = datetools.bday

        ts = self.ts[::3]

        start, end = self.ts.index[3], self.ts.index[6]
        start_missing, end_missing = self.ts.index[2], self.ts.index[7]

        # neither specified
        truncated = ts.truncate()
        assert_series_equal(truncated, ts)

        # both specified
        expected = ts[1:3]

        truncated = ts.truncate(start, end)
        assert_series_equal(truncated, expected)

        truncated = ts.truncate(start_missing, end_missing)
        assert_series_equal(truncated, expected)

        # start specified
        expected = ts[1:]

        truncated = ts.truncate(before=start)
        assert_series_equal(truncated, expected)

        truncated = ts.truncate(before=start_missing)
        assert_series_equal(truncated, expected)

        # end specified
        expected = ts[:3]

        truncated = ts.truncate(after=end)
        assert_series_equal(truncated, expected)

        truncated = ts.truncate(after=end_missing)
        assert_series_equal(truncated, expected)

        # corner case, empty series returned
        truncated = ts.truncate(after=self.ts.index[0] - offset)
        assert(len(truncated) == 0)

        truncated = ts.truncate(before=self.ts.index[-1] + offset)
        assert(len(truncated) == 0)

        truncated = ts.truncate(before=self.ts.index[-1] + offset,
                                after=self.ts.index[0] - offset)
        assert(len(truncated) == 0)

    def test_asOf(self):
        self.ts[5:10] = np.NaN
        self.ts[15:20] = np.NaN

        val1 = self.ts.asOf(self.ts.index[7])
        val2 = self.ts.asOf(self.ts.index[19])

        self.assertEqual(val1, self.ts[4])
        self.assertEqual(val2, self.ts[14])

        # accepts strings
        val1 = self.ts.asOf(str(self.ts.index[7]))
        self.assertEqual(val1, self.ts[4])

        # in there
        self.assertEqual(self.ts.asOf(self.ts.index[3]), self.ts[3])

        # no as of value
        d = self.ts.index[0] - datetools.bday
        self.assert_(np.isnan(self.ts.asOf(d)))

    def test_merge(self):
        index, data = common.getMixedTypeDict()

        source = Series(data['B'], index=data['C'])
        target = Series(data['C'][:4], index=data['D'][:4])

        merged = target.merge(source)

        for k, v in merged.iteritems():
            self.assertEqual(v, source[target[k]])

        # input could be a dict
        merged = target.merge(source.toDict())

        for k, v in merged.iteritems():
            self.assertEqual(v, source[target[k]])

    def test_merge_int(self):
        left = Series({'a' : 1., 'b' : 2., 'c' : 3., 'd' : 4})
        right = Series({1 : 11, 2 : 22, 3 : 33})

        self.assert_(left.dtype == np.float_)
        self.assert_(issubclass(right.dtype.type, np.integer))

        merged = left.merge(right)
        self.assert_(merged.dtype == np.float_)
        self.assert_(isnull(merged['d']))
        self.assert_(not isnull(merged['c']))

    def test_apply(self):
        assert_series_equal(self.ts.apply(np.sqrt), np.sqrt(self.ts))

        # elementwise-apply
        import math
        assert_series_equal(self.ts.apply(math.exp), np.exp(self.ts))

    def test_reindex(self):
        identity = self.series.reindex(self.series.index)
        self.assertEqual(id(self.series.index), id(identity.index))

        subIndex = self.series.index[10:20]
        subSeries = self.series.reindex(subIndex)

        for idx, val in subSeries.iteritems():
            self.assertEqual(val, self.series[idx])

        subIndex2 = self.ts.index[10:20]
        subTS = self.ts.reindex(subIndex2)

        for idx, val in subTS.iteritems():
            self.assertEqual(val, self.ts[idx])
        stuffSeries = self.ts.reindex(subIndex)

        self.assert_(np.isnan(stuffSeries).all())

        # This is extremely important for the Cython code to not screw up
        nonContigIndex = self.ts.index[::2]
        subNonContig = self.ts.reindex(nonContigIndex)
        for idx, val in subNonContig.iteritems():
            self.assertEqual(val, self.ts[idx])

    def test_reindex_corner(self):
        # (don't forget to fix this) I think it's fixed
        reindexed_dep = self.empty.reindex(self.ts.index, method='pad')

        # corner case: pad empty series
        reindexed = self.empty.reindex(self.ts.index, method='pad')

        # pass non-Index
        reindexed = self.ts.reindex(list(self.ts.index))
        assert_series_equal(self.ts, reindexed)

        # bad fill method
        ts = self.ts[::2]
        self.assertRaises(Exception, ts.reindex, self.ts.index, method='foo')

    def test_reindex_pad(self):
        s = Series(np.arange(10), np.arange(10))

        s2 = s[::2]

        reindexed = s2.reindex(s.index, method='pad')
        reindexed2 = s2.reindex(s.index, method='ffill')
        assert_series_equal(reindexed, reindexed2)

        expected = Series([0, 0, 2, 2, 4, 4, 6, 6, 8, 8], index=np.arange(10))
        assert_series_equal(reindexed, expected)

    def test_reindex_backfill(self):
        pass

    def test_reindex_int(self):
        ts = self.ts[::2]
        int_ts = Series(np.zeros(len(ts), dtype=int), index=ts.index)

        # this should work fine
        reindexed_int = int_ts.reindex(self.ts.index)

        # if NaNs introduced
        self.assert_(reindexed_int.dtype == np.float_)

        # NO NaNs introduced
        reindexed_int = int_ts.reindex(int_ts.index[::2])
        self.assert_(reindexed_int.dtype == np.int_)

    def test_reindex_bool(self):

        # A series other than float, int, string, or object
        ts = self.ts[::2]
        bool_ts = Series(np.zeros(len(ts), dtype=bool), index=ts.index)

        # this should work fine
        reindexed_bool = bool_ts.reindex(self.ts.index)

        # if NaNs introduced
        self.assert_(reindexed_bool.dtype == np.object_)

        # NO NaNs introduced
        reindexed_bool = bool_ts.reindex(bool_ts.index[::2])
        self.assert_(reindexed_bool.dtype == np.bool_)

    def test_reindex_bool_pad(self):
        # fail
        ts = self.ts[5:]
        bool_ts = Series(np.zeros(len(ts), dtype=bool), index=ts.index)
        filled_bool = bool_ts.reindex(self.ts.index, method='pad')
        self.assert_(isnull(filled_bool[:5]).all())

    def test_reindex_like(self):
        other = self.ts[::2]
        assert_series_equal(self.ts.reindex(other.index),
                            self.ts.reindex_like(other))

    def test_rename(self):
        renamer = lambda x: x.strftime('%Y%m%d')
        renamed = self.ts.rename(renamer)
        self.assertEqual(renamed.index[0], renamer(self.ts.index[0]))

        # dict
        rename_dict = dict(zip(self.ts.index, renamed.index))
        renamed2 = self.ts.rename(rename_dict)
        assert_series_equal(renamed, renamed2)

    def test_preserveRefs(self):
        sl = self.ts[5:10]
        seq = self.ts[[5,10,15]]
        sl[4] = np.NaN
        seq[1] = np.NaN
        self.assertFalse(np.isnan(self.ts[9]))
        self.assertFalse(np.isnan(self.ts[10]))

    def test_ne(self):
        ts = TimeSeries([3, 4, 5, 6, 7], [3, 4, 5, 6, 7], dtype=float)
        expected = [True, True, False, True, True]
        self.assert_(common.equalContents(ts.index != 5, expected))
        self.assert_(common.equalContents(~(ts.index == 5), expected))

    def test_pad_nan(self):
        x = TimeSeries([np.nan, 1., np.nan, 3., np.nan],
                       ['z', 'a', 'b', 'c', 'd'], dtype=float)
        x = x.fillna(method='pad')
        expected = TimeSeries([np.nan, 1.0, 1.0, 3.0, 3.0],
                                ['z', 'a', 'b', 'c', 'd'], dtype=float)
        assert_series_equal(x[1:], expected[1:])
        self.assert_(np.isnan(x[0]), np.isnan(expected[0]))

    def test_unstack(self):
        from numpy import nan
        from pandas.util.testing import assert_frame_equal

        index = MultiIndex(levels=[['bar', 'foo'], ['one', 'three', 'two']],
                           labels=[[1, 1, 0, 0], [0, 1, 0, 2]])

        s = Series(np.arange(4.), index=index)
        unstacked = s.unstack()

        expected = DataFrame([[2., nan, 3.], [0., 1., nan]],
                             index=['bar', 'foo'],
                             columns=['one', 'three', 'two'])

        assert_frame_equal(unstacked, expected)

        unstacked = s.unstack(level=0)
        assert_frame_equal(unstacked, expected.T)

        index = MultiIndex(levels=[['bar'], ['one', 'two', 'three'], [0, 1]],
                           labels=[[0, 0, 0, 0, 0, 0],
                                   [0, 1, 2, 0, 1, 2],
                                   [0, 1, 0, 1, 0, 1]])
        s = Series(np.random.randn(6), index=index)
        exp_index = MultiIndex(levels=[['one', 'two', 'three'], [0, 1]],
                               labels=[[0, 1, 2, 0, 1, 2],
                                       [0, 1, 0, 1, 0, 1]])
        expected = DataFrame({'bar' : s.values}, index=exp_index).sortlevel(0)
        unstacked = s.unstack(0)
        assert_frame_equal(unstacked, expected)

#-------------------------------------------------------------------------------
# TimeSeries-specific

    def test_fillna(self):
        ts = Series([0., 1., 2., 3., 4.], index=common.makeDateIndex(5))

        self.assert_(np.array_equal(ts, ts.fillna()))

        ts[2] = np.NaN

        self.assert_(np.array_equal(ts.fillna(), [0., 1., 1., 3., 4.]))
        self.assert_(np.array_equal(ts.fillna(method='backfill'),
                                    [0., 1., 3., 3., 4.]))

        self.assert_(np.array_equal(ts.fillna(value=5), [0., 1., 5., 3., 4.]))

    def test_fillna_bug(self):
        x = Series([nan, 1., nan, 3., nan],['z','a','b','c','d'])
        filled = x.fillna(method='ffill')
        expected = Series([nan, 1., 1., 3., 3.], x.index)
        assert_series_equal(filled, expected)

        filled = x.fillna(method='bfill')
        expected = Series([1., 1., 3., 3., nan], x.index)
        assert_series_equal(filled, expected)

    def test_asfreq(self):
        ts = Series([0., 1., 2.], index=[datetime(2009, 10, 30),
                                         datetime(2009, 11, 30),
                                         datetime(2009, 12, 31)])

        daily_ts = ts.asfreq('WEEKDAY')
        monthly_ts = daily_ts.asfreq('EOM')
        self.assert_(np.array_equal(monthly_ts, ts))

        daily_ts = ts.asfreq('WEEKDAY', method='pad')
        monthly_ts = daily_ts.asfreq('EOM')
        self.assert_(np.array_equal(monthly_ts, ts))

        daily_ts = ts.asfreq(datetools.bday)
        monthly_ts = daily_ts.asfreq(datetools.bmonthEnd)
        self.assert_(np.array_equal(monthly_ts, ts))

    def test_interpolate(self):
        ts = Series(np.arange(len(self.ts), dtype=float), self.ts.index)

        ts_copy = ts.copy()
        ts_copy[5:10] = np.NaN

        linear_interp = ts_copy.interpolate(method='linear')
        self.assert_(np.array_equal(linear_interp, ts))

        ord_ts = Series([d.toordinal() for d in self.ts.index],
                        index=self.ts.index).astype(float)

        ord_ts_copy = ord_ts.copy()
        ord_ts_copy[5:10] = np.NaN

        time_interp = ord_ts_copy.interpolate(method='time')
        self.assert_(np.array_equal(time_interp, ord_ts))

        # try time interpolation on a non-TimeSeries
        self.assertRaises(Exception, self.series.interpolate, method='time')

    def test_weekday(self):
        # Just run the function
        weekdays = self.ts.weekday

    def test_diff(self):
        # Just run the function
        self.ts.diff()

    def test_autocorr(self):
        # Just run the function
        self.ts.autocorr()

    def test_first_last_valid(self):
        ts = self.ts.copy()
        ts[:5] = np.NaN

        index = ts.first_valid_index()
        self.assertEqual(index, ts.index[5])

        ts[-5:] = np.NaN
        index = ts.last_valid_index()
        self.assertEqual(index, ts.index[-6])

        ts[:] = np.nan
        self.assert_(ts.last_valid_index() is None)
        self.assert_(ts.first_valid_index() is None)

        ser = Series([], index=[])
        self.assert_(ser.last_valid_index() is None)
        self.assert_(ser.first_valid_index() is None)

#-------------------------------------------------------------------------------
# GroupBy

    def test_select(self):
        n = len(self.ts)
        result = self.ts.select(lambda x: x >= self.ts.index[n // 2])
        expected = self.ts.reindex(self.ts.index[n//2:])
        assert_series_equal(result, expected)

        result = self.ts.select(lambda x: x.weekday() == 2)
        expected = self.ts[self.ts.weekday == 2]
        assert_series_equal(result, expected)

if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

