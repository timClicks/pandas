# pylint: disable-msg=W0612,E1101
from copy import deepcopy
from datetime import datetime, timedelta
from StringIO import StringIO
import cPickle as pickle
import operator
import os
import unittest

from numpy import random, nan
from numpy.random import randn
import numpy as np

import pandas.core.datetools as datetools
from pandas.core.index import NULL_INDEX
from pandas.core.api import (DataFrame, Index, Series, notnull, isnull)

from pandas.util.testing import (assert_almost_equal,
                                 assert_series_equal,
                                 assert_frame_equal,
                                 randn)

import pandas.util.testing as tm

#-------------------------------------------------------------------------------
# DataFrame test cases

class CheckIndexing(object):

    def test_getitem(self):
        # slicing

        sl = self.frame[:20]
        self.assertEqual(20, len(sl.index))

        # column access

        for _, series in sl.iteritems():
            self.assertEqual(20, len(series.index))
            self.assert_(tm.equalContents(series.index, sl.index))

        for key, _ in self.frame._series.iteritems():
            self.assert_(self.frame[key] is not None)

        self.assert_('random' not in self.frame)
        self.assertRaises(Exception, self.frame.__getitem__, 'random')

    def test_getitem_iterator(self):
        idx = iter(['A', 'B', 'C'])
        result = self.frame.ix[:, idx]
        expected = self.frame.ix[:, ['A', 'B', 'C']]
        assert_frame_equal(result, expected)

    def test_getitem_boolean(self):
        # boolean indexing
        d = self.tsframe.index[10]
        indexer = self.tsframe.index > d
        indexer_obj = indexer.astype(object)

        subindex = self.tsframe.index[indexer]
        subframe = self.tsframe[indexer]

        self.assert_(np.array_equal(subindex, subframe.index))
        self.assertRaises(Exception, self.tsframe.__getitem__, indexer[:-1])

        subframe_obj = self.tsframe[indexer_obj]
        assert_frame_equal(subframe_obj, subframe)

    def test_setitem(self):
        # not sure what else to do here
        series = self.frame['A'][::2]
        self.frame['col5'] = series
        self.assert_('col5' in self.frame)
        tm.assert_dict_equal(series, self.frame['col5'],
                                 compare_keys=False)

        series = self.frame['A']
        self.frame['col6'] = series
        tm.assert_dict_equal(series, self.frame['col6'],
                                 compare_keys=False)

        self.assertRaises(Exception, self.frame.__setitem__,
                          randn(len(self.frame) + 1))

        # set ndarray
        arr = randn(len(self.frame))
        self.frame['col9'] = arr
        self.assert_((self.frame['col9'] == arr).all())

        self.frame['col7'] = 5
        assert((self.frame['col7'] == 5).all())

        self.frame['col0'] = 3.14
        assert((self.frame['col0'] == 3.14).all())

        self.frame['col8'] = 'foo'
        assert((self.frame['col8'] == 'foo').all())

        smaller = self.frame[:2]
        smaller['col10'] = ['1', '2']
        self.assertEqual(smaller['col10'].dtype, np.object_)
        self.assert_((smaller['col10'] == ['1', '2']).all())

    def test_setitem_tuple(self):
        self.frame['A', 'B'] = self.frame['A']
        assert_series_equal(self.frame['A', 'B'], self.frame['A'])

    def test_setitem_always_copy(self):
        s = self.frame['A'].copy()
        self.frame['E'] = s

        self.frame['E'][5:10] = nan
        self.assert_(notnull(s[5:10]).all())

    def test_setitem_boolean(self):
        df = self.frame.copy()
        values = self.frame.values

        df[df > 0] = 5
        values[values > 0] = 5
        assert_almost_equal(df.values, values)

        df[df == 5] = 0
        values[values == 5] = 0
        assert_almost_equal(df.values, values)

        self.assertRaises(Exception, df.__setitem__, df[:-1] > 0, 2)
        self.assertRaises(Exception, df.__setitem__, df * 0, 2)

        # index with DataFrame
        mask = df > np.abs(df)
        expected = df.copy()
        df[df > np.abs(df)] = nan
        expected.values[mask.values] = nan
        assert_frame_equal(df, expected)

    def test_setitem_boolean_column(self):
        expected = self.frame.copy()
        mask = self.frame['A'] > 0

        self.frame.ix[mask, 'B'] = 0
        expected.values[mask, 1] = 0

        assert_frame_equal(self.frame, expected)

    def test_setitem_corner(self):
        # corner case
        df = DataFrame({'B' : [1., 2., 3.],
                         'C' : ['a', 'b', 'c']},
                        index=np.arange(3))
        del df['B']
        df['B'] = [1., 2., 3.]
        self.assert_('B' in df)
        self.assertEqual(len(df.columns), 2)

        df['A'] = 'beginning'
        df['E'] = 'foo'
        df['D'] = 'bar'
        df[datetime.now()] = 'date'
        df[datetime.now()] = 5.

        # what to do when empty frame with index
        dm = DataFrame(index=self.frame.index)
        dm['A'] = 'foo'
        dm['B'] = 'bar'
        self.assertEqual(len(dm.columns), 2)
        self.assertEqual(dm.values.dtype, np.object_)

        dm['C'] = 1
        self.assertEqual(dm['C'].dtype, np.int_)

        # set existing column
        dm['A'] = 'bar'
        self.assertEqual('bar', dm['A'][0])

        dm = DataFrame(index=np.arange(3))
        dm['A'] = 1
        dm['foo'] = 'bar'
        del dm['foo']
        dm['foo'] = 'bar'
        self.assertEqual(dm['foo'].dtype, np.object_)

        dm['coercable'] = ['1', '2', '3']
        self.assertEqual(dm['coercable'].dtype, np.object_)

    def test_setitem_ambig(self):
        # difficulties with mixed-type data
        from decimal import Decimal

        # created as float type
        dm = DataFrame(index=range(3), columns=range(3))

        coercable_series = Series([Decimal(1) for _ in range(3)],
                                  index=range(3))
        uncoercable_series = Series(['foo', 'bzr', 'baz'], index=range(3))

        dm[0] = np.ones(3)
        self.assertEqual(len(dm.columns), 3)
        # self.assert_(dm.objects is None)

        dm[1] = coercable_series
        self.assertEqual(len(dm.columns), 3)
        # self.assert_(dm.objects is None)

        dm[2] = uncoercable_series
        self.assertEqual(len(dm.columns), 3)
        # self.assert_(dm.objects is not None)
        self.assert_(dm[2].dtype == np.object_)

    def test_delitem_corner(self):
        f = self.frame.copy()
        del f['D']
        self.assertEqual(len(f.columns), 3)
        self.assertRaises(KeyError, f.__delitem__, 'D')
        del f['B']
        self.assertEqual(len(f.columns), 2)

    def test_getitem_fancy_2d(self):
        f = self.frame
        ix = f.ix

        assert_frame_equal(ix[:, ['B', 'A']], f.reindex(columns=['B', 'A']))

        subidx = self.frame.index[[5, 4, 1]]
        assert_frame_equal(ix[subidx, ['B', 'A']],
                           f.reindex(index=subidx, columns=['B', 'A']))

        # slicing rows, etc.
        assert_frame_equal(ix[5:10], f[5:10])
        assert_frame_equal(ix[5:10, :], f[5:10])
        assert_frame_equal(ix[:5, ['A', 'B']],
                           f.reindex(index=f.index[:5], columns=['A', 'B']))

        # slice rows with labels, inclusive!
        expected = ix[5:11]
        result = ix[f.index[5]:f.index[10]]
        assert_frame_equal(expected, result)

        # slice columns
        assert_frame_equal(ix[:, :2], f.reindex(columns=['A', 'B']))

        # get view
        exp = f.copy()
        ix[5:10].values[:] = 5
        exp.values[5:10] = 5
        assert_frame_equal(f, exp)

    def test_setitem_fancy_2d(self):
        f = self.frame
        ix = f.ix

        # case 1
        frame = self.frame.copy()
        expected = frame.copy()
        frame.ix[:, ['B', 'A']] = 1
        expected['B'] = 1
        expected['A'] = 1
        assert_frame_equal(frame, expected)

        # case 2
        frame = self.frame.copy()
        frame2 = self.frame.copy()

        expected = frame.copy()

        subidx = self.frame.index[[5, 4, 1]]
        values = randn(3, 2)

        frame.ix[subidx, ['B', 'A']] = values
        frame2.ix[[5, 4, 1], ['B', 'A']] = values

        expected['B'].ix[subidx] = values[:, 0]
        expected['A'].ix[subidx] = values[:, 1]

        assert_frame_equal(frame, expected)
        assert_frame_equal(frame2, expected)

        # case 3: slicing rows, etc.
        frame = self.frame.copy()

        expected1 = self.frame.copy()
        frame.ix[5:10] = 1.
        expected1.values[5:10] = 1.
        assert_frame_equal(frame, expected1)

        expected2 = self.frame.copy()
        arr = randn(5, len(frame.columns))
        frame.ix[5:10] = arr
        expected2.values[5:10] = arr
        assert_frame_equal(frame, expected2)

        # case 4
        frame = self.frame.copy()
        frame.ix[5:10, :] = 1.
        assert_frame_equal(frame, expected1)
        frame.ix[5:10, :] = arr
        assert_frame_equal(frame, expected2)

        # case 5
        frame = self.frame.copy()
        frame2 = self.frame.copy()

        expected = self.frame.copy()
        values = randn(5, 2)

        frame.ix[:5, ['A', 'B']] = values
        expected['A'][:5] = values[:, 0]
        expected['B'][:5] = values[:, 1]
        assert_frame_equal(frame, expected)

        frame2.ix[:5, [0, 1]] = values
        assert_frame_equal(frame2, expected)

        # case 6: slice rows with labels, inclusive!
        frame = self.frame.copy()
        expected = self.frame.copy()

        frame.ix[frame.index[5]:frame.index[10]] = 5.
        expected.values[5:11] = 5
        assert_frame_equal(frame, expected)

        # case 7: slice columns
        frame = self.frame.copy()
        frame2 = self.frame.copy()
        expected = self.frame.copy()

        # slice indices
        frame.ix[:, 1:3] = 4.
        expected.values[:, 1:3] = 4.
        assert_frame_equal(frame, expected)

        # slice with labels
        frame.ix[:, 'B':'C'] = 4.
        assert_frame_equal(frame, expected)

    def test_fancy_setitem_int_labels(self):
        # integer index defers to label-based indexing

        df = DataFrame(np.random.randn(10, 5), index=np.arange(0, 20, 2))

        tmp = df.copy()
        exp = df.copy()
        tmp.ix[[0, 2, 4]] = 5
        exp.values[:3] = 5
        assert_frame_equal(tmp, exp)

        tmp = df.copy()
        exp = df.copy()
        tmp.ix[6] = 5
        exp.values[3] = 5
        assert_frame_equal(tmp, exp)

        tmp = df.copy()
        exp = df.copy()
        tmp.ix[:, 2] = 5
        exp.values[:, 2] = 5
        assert_frame_equal(tmp, exp)

    def test_fancy_getitem_int_labels(self):
        df = DataFrame(np.random.randn(10, 5), index=np.arange(0, 20, 2))

        result = df.ix[[4, 2, 0], [2, 0]]
        expected = df.reindex(index=[4, 2, 0], columns=[2, 0])
        assert_frame_equal(result, expected)

        result = df.ix[[4, 2, 0]]
        expected = df.reindex(index=[4, 2, 0])
        assert_frame_equal(result, expected)

        result = df.ix[4]
        expected = df.xs(4)
        assert_series_equal(result, expected)

        result = df.ix[:, 3]
        expected = df[3]
        assert_series_equal(result, expected)

    def test_fancy_index_int_labels_exceptions(self):
        df = DataFrame(np.random.randn(10, 5), index=np.arange(0, 20, 2))

        # labels that aren't contained
        self.assertRaises(KeyError, df.ix.__setitem__,
                          ([0, 1, 2], [2, 3, 4]), 5)

        # try to set indices not contained in frame
        self.assertRaises(KeyError,
                          self.frame.ix.__setitem__,
                          ['foo', 'bar', 'baz'], 1)
        self.assertRaises(KeyError,
                          self.frame.ix.__setitem__,
                          (slice(None, None), ['E']), 1)
        self.assertRaises(KeyError,
                          self.frame.ix.__setitem__,
                          (slice(None, None), 'E'), 1)

    def test_setitem_fancy_mixed_2d(self):
        self.assertRaises(Exception, self.mixed_frame.ix.__setitem__,
                          (slice(0, 5), ['C', 'B', 'A']), 5)

    def test_getitem_fancy_1d(self):
        f = self.frame
        ix = f.ix

        # return self if no slicing...for now
        self.assert_(ix[:, :] is f)

        # low dimensional slice
        xs1 = ix[2, ['C', 'B', 'A']]
        xs2 = f.xs(f.index[2]).reindex(['C', 'B', 'A'])
        assert_series_equal(xs1, xs2)

        ts1 = ix[5:10, 2]
        ts2 = f[f.columns[2]][5:10]
        assert_series_equal(ts1, ts2)

        # positional xs
        xs1 = ix[0]
        xs2 = f.xs(f.index[0])
        assert_series_equal(xs1, xs2)

        xs1 = ix[f.index[5]]
        xs2 = f.xs(f.index[5])
        assert_series_equal(xs1, xs2)

        # single column
        assert_series_equal(ix[:, 'A'], f['A'])

        # return view
        exp = f.copy()
        exp.values[5] = 4
        ix[5][:] = 4
        assert_frame_equal(exp, f)

        exp.values[:, 1] = 6
        ix[:, 1][:] = 6
        assert_frame_equal(exp, f)

        # slice of mixed-frame
        xs = self.mixed_frame.ix[5]
        exp = self.mixed_frame.xs(self.mixed_frame.index[5])
        assert_series_equal(xs, exp)

    def test_setitem_fancy_1d(self):
        # case 1: set cross-section for indices
        frame = self.frame.copy()
        expected = self.frame.copy()

        frame.ix[2, ['C', 'B', 'A']] = [1., 2., 3.]
        expected['C'][2] = 1.
        expected['B'][2] = 2.
        expected['A'][2] = 3.
        assert_frame_equal(frame, expected)

        frame2 = self.frame.copy()
        frame2.ix[2, [3, 2, 1]] = [1., 2., 3.]
        assert_frame_equal(frame, expected)

        # case 2, set a section of a column
        frame = self.frame.copy()
        expected = self.frame.copy()

        vals = randn(5)
        expected.values[5:10, 2] = vals
        frame.ix[5:10, 2] = vals
        assert_frame_equal(frame, expected)

        frame2 = self.frame.copy()
        frame2.ix[5:10, 'B'] = vals
        assert_frame_equal(frame, expected)

        # case 3: full xs
        frame = self.frame.copy()
        expected = self.frame.copy()

        frame.ix[4] = 5.
        expected.values[4] = 5.
        assert_frame_equal(frame, expected)

        frame.ix[frame.index[4]] = 6.
        expected.values[4] = 6.
        assert_frame_equal(frame, expected)

        # single column
        frame = self.frame.copy()
        expected = self.frame.copy()

        frame.ix[:, 'A'] = 7.
        expected['A'] = 7.
        assert_frame_equal(frame, expected)

    def test_getitem_fancy_scalar(self):
        f = self.frame
        ix = f.ix
        # individual value
        for col in f.columns:
            ts = f[col]
            for idx in f.index[::5]:
                assert_almost_equal(ix[idx, col], ts[idx])

    def test_setitem_fancy_scalar(self):
        f = self.frame
        expected = self.frame.copy()
        ix = f.ix
        # individual value
        for j, col in enumerate(f.columns):
            ts = f[col]
            for idx in f.index[::5]:
                i = f.index.get_loc(idx)
                val = randn()
                expected.values[i,j] = val
                ix[idx, col] = val
                assert_frame_equal(f, expected)

    def test_getitem_fancy_boolean(self):
        f = self.frame
        ix = f.ix

        expected = f.reindex(columns=['B', 'D'])
        result = ix[:, [False, True, False, True]]
        assert_frame_equal(result, expected)

        expected = f.reindex(index=f.index[5:10], columns=['B', 'D'])
        result = ix[5:10, [False, True, False, True]]
        assert_frame_equal(result, expected)

        boolvec = f.index > f.index[7]
        expected = f.reindex(index=f.index[boolvec])
        result = ix[boolvec]
        assert_frame_equal(result, expected)
        result = ix[boolvec, :]
        assert_frame_equal(result, expected)

        result = ix[boolvec, 2:]
        expected = f.reindex(index=f.index[boolvec],
                             columns=['C', 'D'])
        assert_frame_equal(result, expected)

    def test_setitem_fancy_boolean(self):
        # from 2d, set with booleans
        frame = self.frame.copy()
        expected = self.frame.copy()

        mask = frame['A'] > 0
        frame.ix[mask] = 0.
        expected.values[mask] = 0.
        assert_frame_equal(frame, expected)

        frame = self.frame.copy()
        expected = self.frame.copy()
        frame.ix[mask, ['A', 'B']] = 0.
        expected.values[mask, :2] = 0.
        assert_frame_equal(frame, expected)

    def test_getitem_fancy_ints(self):
        result = self.frame.ix[[1,4,7]]
        expected = self.frame.ix[self.frame.index[[1,4,7]]]
        assert_frame_equal(result, expected)

        result = self.frame.ix[:, [2, 0, 1]]
        expected = self.frame.ix[:, self.frame.columns[[2, 0, 1]]]
        assert_frame_equal(result, expected)

    def test_getitem_setitem_fancy_exceptions(self):
        ix = self.frame.ix
        self.assertRaises(Exception, ix.__getitem__,
                          (slice(None, None, None),
                           slice(None, None, None),
                           slice(None, None, None)))
        self.assertRaises(Exception, ix.__setitem__,
                          (slice(None, None, None),
                           slice(None, None, None),
                           slice(None, None, None)), 1)

        # boolean index misaligned labels
        mask = self.frame['A'][::-1] > 1
        self.assertRaises(Exception, ix.__getitem__, mask)
        self.assertRaises(Exception, ix.__setitem__, mask, 1.)

    def test_setitem_fancy_exceptions(self):
        pass

    def test_getitem_boolean_missing(self):
        pass

    def test_setitem_boolean_missing(self):
        pass

class TestDataFrame(unittest.TestCase, CheckIndexing):
    klass = DataFrame

    def setUp(self):
        self.seriesd = tm.getSeriesData()
        self.tsd = tm.getTimeSeriesData()

        self.frame = DataFrame(self.seriesd)
        self.frame2 = DataFrame(self.seriesd, columns=['D', 'C', 'B', 'A'])
        self.intframe = DataFrame(dict((k, v.astype(int))
                                        for k, v in self.seriesd.iteritems()))

        self.tsframe = DataFrame(self.tsd)

        self.mixed_frame = self.frame.copy()
        self.mixed_frame['foo'] = 'bar'

        self.ts1 = tm.makeTimeSeries()
        self.ts2 = tm.makeTimeSeries()[5:]
        self.ts3 = tm.makeTimeSeries()[-5:]
        self.ts4 = tm.makeTimeSeries()[1:-1]

        self.ts_dict = {
            'col1' : self.ts1,
            'col2' : self.ts2,
            'col3' : self.ts3,
            'col4' : self.ts4,
        }
        self.empty = DataFrame({})

        self.unsortable = DataFrame(
            {'foo' : [1] * 1000,
             datetime.today() : [1] * 1000,
             'bar' : ['bar'] * 1000,
             datetime.today() + timedelta(1) : ['bar'] * 1000},
            index=np.arange(1000))

        arr = np.array([[1., 2., 3.],
                        [4., 5., 6.],
                        [7., 8., 9.]])

        self.simple = DataFrame(arr, columns=['one', 'two', 'three'],
                                 index=['a', 'b', 'c'])

    def test_get_axis(self):
        self.assert_(DataFrame._get_axis_name(0) == 'index')
        self.assert_(DataFrame._get_axis_name(1) == 'columns')
        self.assert_(DataFrame._get_axis_name('index') == 'index')
        self.assert_(DataFrame._get_axis_name('columns') == 'columns')
        self.assertRaises(Exception, DataFrame._get_axis_name, 'foo')
        self.assertRaises(Exception, DataFrame._get_axis_name, None)

        self.assert_(DataFrame._get_axis_number(0) == 0)
        self.assert_(DataFrame._get_axis_number(1) == 1)
        self.assert_(DataFrame._get_axis_number('index') == 0)
        self.assert_(DataFrame._get_axis_number('columns') == 1)
        self.assertRaises(Exception, DataFrame._get_axis_number, 2)
        self.assertRaises(Exception, DataFrame._get_axis_number, None)

        self.assert_(self.frame._get_axis(0) is self.frame.index)
        self.assert_(self.frame._get_axis(1) is self.frame.columns)

    def test_set_index(self):
        idx = Index(np.arange(len(self.mixed_frame)))
        self.mixed_frame.index = idx
        self.assert_(self.mixed_frame['foo'].index  is idx)
        self.assertRaises(Exception, setattr, self.mixed_frame, 'index',
                          idx[::2])

    def test_set_columns(self):
        cols = Index(np.arange(len(self.mixed_frame.columns)))
        self.mixed_frame.columns = cols
        self.assertRaises(Exception, setattr, self.mixed_frame, 'columns',
                          cols[::2])

    def test_constructor(self):
        df = DataFrame()
        self.assert_(len(df.index) == 0)

        df = DataFrame(data={})
        self.assert_(len(df.index) == 0)

    def test_constructor_mixed(self):
        index, data = tm.getMixedTypeDict()

        indexed_frame = DataFrame(data, index=index)
        unindexed_frame = DataFrame(data)

        self.assertEqual(self.mixed_frame['foo'].dtype, np.object_)

    def test_constructor_rec(self):
        rec = self.frame.to_records(index=False)

        # Assigning causes segfault in NumPy < 1.5.1
        # rec.dtype.names = list(rec.dtype.names)[::-1]

        index = self.frame.index

        df = DataFrame(rec)
        self.assert_(np.array_equal(df.columns, rec.dtype.names))

        df2 = DataFrame(rec, index=index)
        self.assert_(np.array_equal(df2.columns, rec.dtype.names))
        self.assert_(df2.index.equals(index))

    def test_constructor_bool(self):
        df = DataFrame({0 : np.ones(10, dtype=bool),
                        1 : np.zeros(10, dtype=bool)})
        self.assertEqual(df.values.dtype, np.bool_)

    def test_is_mixed_type(self):
        self.assert_(not self.frame._is_mixed_type)
        self.assert_(self.mixed_frame._is_mixed_type)

    def test_constructor_dict(self):
        frame = DataFrame({'col1' : self.ts1,
                            'col2' : self.ts2})

        tm.assert_dict_equal(self.ts1, frame['col1'], compare_keys=False)
        tm.assert_dict_equal(self.ts2, frame['col2'], compare_keys=False)

        frame = DataFrame({'col1' : self.ts1,
                            'col2' : self.ts2},
                           columns=['col2', 'col3', 'col4'])

        self.assertEqual(len(frame), len(self.ts2))
        self.assert_('col1' not in frame)
        self.assert_(np.isnan(frame['col3']).all())

        # Corner cases
        self.assertEqual(len(DataFrame({})), 0)
        self.assertRaises(Exception, lambda x: DataFrame([self.ts1, self.ts2]))

        # pass dict and array, nicht nicht
        self.assertRaises(Exception, DataFrame,
                          {'A' : {'a' : 'a', 'b' : 'b'},
                           'B' : ['a', 'b']})

        # can I rely on the order?
        self.assertRaises(Exception, DataFrame,
                          {'A' : ['a', 'b'],
                           'B' : {'a' : 'a', 'b' : 'b'}})
        self.assertRaises(Exception, DataFrame,
                          {'A' : ['a', 'b'],
                           'B' : Series(['a', 'b'], index=['a', 'b'])})

        # Length-one dict micro-optimization
        frame = DataFrame({'A' : {'1' : 1, '2' : 2}})
        self.assert_(np.array_equal(frame.index, ['1', '2']))

        # empty dict plus index
        idx = Index([0, 1, 2])
        frame = DataFrame({}, index=idx)
        self.assert_(frame.index is idx)

        # empty with index and columns
        idx = Index([0, 1, 2])
        frame = DataFrame({}, index=idx, columns=idx)
        self.assert_(frame.index is idx)
        self.assert_(frame.columns is idx)
        self.assertEqual(len(frame._series), 3)

    def test_constructor_dict_block(self):
        expected = [[4., 3., 2., 1.]]
        df = DataFrame({'d' : [4.],'c' : [3.],'b' : [2.],'a' : [1.]},
                       columns=['d', 'c', 'b', 'a'])
        assert_almost_equal(df.values, expected)

    def test_constructor_dict_cast(self):
        # cast float tests
        test_data = {
                'A' : {'1' : 1, '2' : 2},
                'B' : {'1' : '1', '2' : '2', '3' : '3'},
        }
        frame = DataFrame(test_data, dtype=float)
        self.assertEqual(len(frame), 3)
        self.assert_(frame['B'].dtype == np.float_)
        self.assert_(frame['A'].dtype == np.float_)

        frame = DataFrame(test_data)
        self.assertEqual(len(frame), 3)
        self.assert_(frame['B'].dtype == np.object_)
        self.assert_(frame['A'].dtype == np.float_)

        # can't cast to float
        test_data = {
                'A' : dict(zip(range(20), tm.makeDateIndex(20))),
                'B' : dict(zip(range(15), randn(15)))
        }
        frame = DataFrame(test_data, dtype=float)
        self.assertEqual(len(frame), 20)
        self.assert_(frame['A'].dtype == np.object_)
        self.assert_(frame['B'].dtype == np.float_)

    def test_constructor_dict_dont_upcast(self):
        d = {'Col1': {'Row1': 'A String', 'Row2': np.nan}}
        df = DataFrame(d)
        self.assert_(isinstance(df['Col1']['Row2'], float))

        dm = DataFrame([[1,2],['a','b']], index=[1,2], columns=[1,2])
        self.assert_(isinstance(dm[1][1], int))

    def test_constructor_ndarray(self):
        mat = np.zeros((2, 3), dtype=float)

        # 2-D input
        frame = DataFrame(mat, columns=['A', 'B', 'C'], index=[1, 2])

        self.assertEqual(len(frame.index), 2)
        self.assertEqual(len(frame.columns), 3)

        # cast type
        frame = DataFrame(mat, columns=['A', 'B', 'C'],
                           index=[1, 2], dtype=int)
        self.assert_(frame.values.dtype == np.int_)

        # 1-D input
        frame = DataFrame(np.zeros(3), columns=['A'], index=[1, 2, 3])
        self.assertEqual(len(frame.index), 3)
        self.assertEqual(len(frame.columns), 1)

        frame = DataFrame(['foo', 'bar'], index=[0, 1], columns=['A'])
        self.assertEqual(len(frame), 2)

        # higher dim raise exception
        self.assertRaises(Exception, DataFrame, np.zeros((3, 3, 3)),
                          columns=['A', 'B', 'C'], index=[1])

        # wrong size axis labels
        self.assertRaises(Exception, DataFrame, mat,
                          columns=['A', 'B', 'C'], index=[1])

        self.assertRaises(Exception, DataFrame, mat,
                          columns=['A', 'B'], index=[1, 2])

        # automatic labeling
        frame = DataFrame(mat)
        self.assert_(np.array_equal(frame.index, range(2)))
        self.assert_(np.array_equal(frame.columns, range(3)))

        frame = DataFrame(mat, index=[1, 2])
        self.assert_(np.array_equal(frame.columns, range(3)))

        frame = DataFrame(mat, columns=['A', 'B', 'C'])
        self.assert_(np.array_equal(frame.index, range(2)))

        # 0-length axis
        frame = DataFrame(np.empty((0, 3)))
        self.assert_(frame.index is NULL_INDEX)

        frame = DataFrame(np.empty((3, 0)))
        self.assert_(len(frame.columns) == 0)

    def test_constructor_corner(self):
        df = DataFrame(index=[])
        self.assertEqual(df.values.shape, (0, 0))

        # empty but with specified dtype
        df = DataFrame(index=range(10), columns=['a','b'], dtype=object)
        self.assert_(df.values.dtype == np.object_)

        # does not error but ends up float
        df = DataFrame(index=range(10), columns=['a','b'], dtype=int)
        self.assert_(df.values.dtype == np.float_)

    def test_constructor_scalar_inference(self):
        data = {'int' : 1, 'bool' : True,
                'float' : 3., 'object' : 'foo'}
        df = DataFrame(data, index=np.arange(10))

        self.assert_(df['int'].dtype == np.int_)
        self.assert_(df['bool'].dtype == np.bool_)
        self.assert_(df['float'].dtype == np.float_)
        self.assert_(df['object'].dtype == np.object_)

    def test_constructor_DataFrame(self):
        df = DataFrame(self.frame)
        assert_frame_equal(df, self.frame)

        df_casted = DataFrame(self.frame, dtype=int)
        self.assert_(df_casted.values.dtype == np.int_)

    def test_constructor_more(self):
        # used to be in test_matrix.py
        arr = randn(10)
        dm = DataFrame(arr, columns=['A'], index=np.arange(10))
        self.assertEqual(dm.values.ndim, 2)

        arr = randn(0)
        dm = DataFrame(arr)
        self.assertEqual(dm.values.ndim, 2)
        self.assertEqual(dm.values.ndim, 2)

        # no data specified
        dm = DataFrame(columns=['A', 'B'], index=np.arange(10))
        self.assertEqual(dm.values.shape, (10, 2))

        dm = DataFrame(columns=['A', 'B'])
        self.assertEqual(dm.values.shape, (0, 2))

        dm = DataFrame(index=np.arange(10))
        self.assertEqual(dm.values.shape, (10, 0))

        # corner, silly
        self.assertRaises(Exception, DataFrame, (1, 2, 3))

        # can't cast
        mat = np.array(['foo', 'bar'], dtype=object).reshape(2, 1)
        self.assertRaises(ValueError, DataFrame, mat, index=[0, 1],
                          columns=[0], dtype=float)

        dm = DataFrame(DataFrame(self.frame._series))
        tm.assert_frame_equal(dm, self.frame)

        # int cast
        dm = DataFrame({'A' : np.ones(10, dtype=int),
                         'B' : np.ones(10, dtype=float)},
                        index=np.arange(10))

        self.assertEqual(len(dm.columns), 2)
        self.assert_(dm.values.dtype == np.float_)

    def test_constructor_ragged(self):
        data = {'A' : randn(10),
                'B' : randn(8)}
        self.assertRaises(Exception, DataFrame, data)

    def test_constructor_scalar(self):
        idx = Index(range(3))
        df = DataFrame({"a" : 0}, index=idx)
        expected = DataFrame({"a" : [0, 0, 0]}, index=idx)
        assert_frame_equal(df, expected)

    def test_astype(self):
        casted = self.frame.astype(int)
        expected = DataFrame(self.frame.values.astype(int),
                             index=self.frame.index,
                             columns=self.frame.columns)
        assert_frame_equal(casted, expected)

        self.frame['foo'] = '5'
        casted = self.frame.astype(int)
        expected = DataFrame(self.frame.values.astype(int),
                             index=self.frame.index,
                             columns=self.frame.columns)
        assert_frame_equal(casted, expected)

    def test_array_interface(self):
        result = np.sqrt(self.frame)
        self.assert_(type(result) is type(self.frame))
        self.assert_(result.index is self.frame.index)
        self.assert_(result.columns is self.frame.columns)

        assert_frame_equal(result, self.frame.apply(np.sqrt))

    def test_pickle(self):
        unpickled = pickle.loads(pickle.dumps(self.mixed_frame))
        assert_frame_equal(self.mixed_frame, unpickled)

        # buglet
        self.mixed_frame._data.ndim

    def test_toDict(self):
        test_data = {
                'A' : {'1' : 1, '2' : 2},
                'B' : {'1' : '1', '2' : '2', '3' : '3'},
        }
        recons_data = DataFrame(test_data).toDict()

        for k, v in test_data.iteritems():
            for k2, v2 in v.iteritems():
                self.assertEqual(v2, recons_data[k][k2])

    def test_from_records(self):
        # from numpy documentation
        arr = np.zeros((2,),dtype=('i4,f4,a10'))
        arr[:] = [(1,2.,'Hello'),(2,3.,"World")]

        frame = DataFrame.from_records(arr)
        indexed_frame = DataFrame.from_records(arr, indexField='f1')

        self.assertRaises(Exception, DataFrame.from_records, np.zeros((2, 3)))

        # what to do?
        records = indexed_frame.to_records()
        self.assertEqual(len(records.dtype.names), 3)

        records = indexed_frame.to_records(index=False)
        self.assertEqual(len(records.dtype.names), 2)
        self.assert_('index' not in records.dtype.names)


    def test_get_agg_axis(self):
        cols = self.frame._get_agg_axis(0)
        self.assert_(cols is self.frame.columns)

        idx = self.frame._get_agg_axis(1)
        self.assert_(idx is self.frame.index)

        self.assertRaises(Exception, self.frame._get_agg_axis, 2)

    def test_nonzero(self):
        self.assertFalse(self.empty)

        self.assert_(self.frame)
        self.assert_(self.mixed_frame)

        # corner case
        df = DataFrame({'A' : [1., 2., 3.],
                         'B' : ['a', 'b', 'c']},
                        index=np.arange(3))
        del df['A']
        self.assert_(df)

    def test_repr(self):
        buf = StringIO()

        # empty
        foo = repr(self.empty)

        # empty with index
        frame = DataFrame(index=np.arange(1000))
        foo = repr(frame)

        # small one
        foo = repr(self.frame)
        self.frame.info(verbose=False, buf=buf)

        # even smaller
        self.frame.reindex(columns=['A']).info(verbose=False, buf=buf)
        self.frame.reindex(columns=['A', 'B']).info(verbose=False, buf=buf)

        # big one
        biggie = DataFrame(np.zeros((1000, 4)), columns=range(4),
                            index=range(1000))
        foo = repr(biggie)

        # mixed
        foo = repr(self.mixed_frame)
        self.mixed_frame.info(verbose=False, buf=buf)

        # big mixed
        biggie = DataFrame({'A' : randn(1000),
                             'B' : tm.makeStringIndex(1000)},
                            index=range(1000))
        biggie['A'][:20] = nan
        biggie['B'][:20] = nan

        foo = repr(biggie)

        # exhausting cases in DataFrame.info

        # columns but no index
        no_index = DataFrame(columns=[0, 1, 3])
        foo = repr(no_index)

        # no columns or index
        self.empty.info(buf=buf)

        # columns are not sortable
        foo = repr(self.unsortable)

        import pandas.core.common as common
        common.set_printoptions(precision=3, column_space=10)
        repr(self.frame)

    def test_head_tail(self):
        assert_frame_equal(self.frame.head(), self.frame[:5])
        assert_frame_equal(self.frame.tail(), self.frame[-5:])

    def test_repr_corner(self):
        # representing infs poses no problems
        df = DataFrame({'foo' : np.inf * np.empty(10)})
        foo = repr(df)

    def test_toString(self):
        # big mixed
        biggie = DataFrame({'A' : randn(1000),
                             'B' : tm.makeStringIndex(1000)},
                            index=range(1000))

        biggie['A'][:20] = nan
        biggie['B'][:20] = nan
        buf = StringIO()
        biggie.toString(buf=buf)

        biggie.toString(buf=buf, columns=['B', 'A'], colSpace=17)
        biggie.toString(buf=buf, columns=['B', 'A'],
                        formatters={'A' : lambda x: '%.1f' % x})

        biggie.toString(buf=buf, columns=['B', 'A'],
                        float_format=str)
        biggie.toString(buf=buf, columns=['B', 'A'], colSpace=12,
                        float_format=str)

        frame = DataFrame(index=np.arange(1000))
        frame.toString(buf=buf)

    def test_toString_unicode_columns(self):
        df = DataFrame({u'\u03c3' : np.arange(10.)})

        buf = StringIO()
        df.toString(buf=buf)
        buf.getvalue()

        buf = StringIO()
        df.info(buf=buf)
        buf.getvalue()

    def test_insert(self):
        df = DataFrame(np.random.randn(5, 3), index=np.arange(5),
                       columns=['c', 'b', 'a'])

        df.insert(0, 'foo', df['a'])
        self.assert_(np.array_equal(df.columns, ['foo', 'c', 'b', 'a']))
        assert_almost_equal(df['a'], df['foo'])

        df.insert(2, 'bar', df['c'])
        self.assert_(np.array_equal(df.columns, ['foo', 'c', 'bar', 'b', 'a']))
        assert_almost_equal(df['c'], df['bar'])

        self.assertRaises(Exception, df.insert, 1, 'a')
        self.assertRaises(Exception, df.insert, 1, 'c')

    def test_delitem(self):
        del self.frame['A']
        self.assert_('A' not in self.frame)

    def test_pop(self):
        A = self.frame.pop('A')
        self.assert_('A' not in self.frame)

        self.frame['foo'] = 'bar'
        foo = self.frame.pop('foo')
        self.assert_('foo' not in self.frame)

    def test_iter(self):
        self.assert_(tm.equalContents(list(self.frame), self.frame.columns))

    def test_len(self):
        self.assertEqual(len(self.frame), len(self.frame.index))

    def test_operators(self):
        garbage = random.random(4)
        colSeries = Series(garbage, index=np.array(self.frame.columns))

        idSum = self.frame + self.frame
        seriesSum = self.frame + colSeries

        for col, series in idSum.iteritems():
            for idx, val in series.iteritems():
                origVal = self.frame[col][idx] * 2
                if not np.isnan(val):
                    self.assertEqual(val, origVal)
                else:
                    self.assert_(np.isnan(origVal))

        for col, series in seriesSum.iteritems():
            for idx, val in series.iteritems():
                origVal = self.frame[col][idx] + colSeries[col]
                if not np.isnan(val):
                    self.assertEqual(val, origVal)
                else:
                    self.assert_(np.isnan(origVal))

        added = self.frame2 + self.frame2
        expected = self.frame2 * 2
        assert_frame_equal(added, expected)

    def test_neg(self):
        # what to do?
        assert_frame_equal(-self.frame, -1 * self.frame)

    def test_first_last_valid(self):
        N = len(self.frame.index)
        mat = randn(N)
        mat[:5] = nan
        mat[-5:] = nan

        frame = DataFrame({'foo' : mat}, index=self.frame.index)
        index = frame.first_valid_index()

        self.assert_(index == frame.index[5])

        index = frame.last_valid_index()
        self.assert_(index == frame.index[-6])

    def test_arith_flex_frame(self):
        res_add = self.frame.add(self.frame)
        res_sub = self.frame.sub(self.frame)
        res_mul = self.frame.mul(self.frame)
        res_div = self.frame.div(2 * self.frame)

        assert_frame_equal(res_add, self.frame + self.frame)
        assert_frame_equal(res_sub, self.frame - self.frame)
        assert_frame_equal(res_mul, self.frame * self.frame)
        assert_frame_equal(res_div, self.frame / (2 * self.frame))

        const_add = self.frame.add(1)
        assert_frame_equal(const_add, self.frame + 1)

    def test_arith_flex_series(self):
        df = self.simple

        row = df.xs('a')
        col = df['two']

        assert_frame_equal(df.add(row), df + row)
        assert_frame_equal(df.add(row, axis=None), df + row)
        assert_frame_equal(df.sub(row), df - row)
        assert_frame_equal(df.div(row), df / row)
        assert_frame_equal(df.mul(row), df * row)

        assert_frame_equal(df.add(col, axis=0), (df.T + col).T)
        assert_frame_equal(df.sub(col, axis=0), (df.T - col).T)
        assert_frame_equal(df.div(col, axis=0), (df.T / col).T)
        assert_frame_equal(df.mul(col, axis=0), (df.T * col).T)

    def test_combineFrame(self):
        frame_copy = self.frame.reindex(self.frame.index[::2])

        del frame_copy['D']
        frame_copy['C'][:5] = nan

        added = self.frame + frame_copy
        tm.assert_dict_equal(added['A'].valid(),
                                 self.frame['A'] * 2,
                                 compare_keys=False)

        self.assert_(np.isnan(added['C'].reindex(frame_copy.index)[:5]).all())

        # assert(False)

        self.assert_(np.isnan(added['D']).all())

        self_added = self.frame + self.frame
        self.assert_(self_added.index.equals(self.frame.index))

        added_rev = frame_copy + self.frame
        self.assert_(np.isnan(added['D']).all())

        # corner cases

        # empty
        plus_empty = self.frame + self.empty
        self.assert_(np.isnan(plus_empty.values).all())

        empty_plus = self.empty + self.frame
        self.assert_(np.isnan(empty_plus.values).all())

        empty_empty = self.empty + self.empty
        self.assert_(not empty_empty)

        # out of order
        reverse = self.frame.reindex(columns=self.frame.columns[::-1])

        assert_frame_equal(reverse + self.frame, self.frame * 2)

    def test_combineSeries(self):

        # Series
        series = self.frame.xs(self.frame.index[0])

        added = self.frame + series

        for key, s in added.iteritems():
            assert_series_equal(s, self.frame[key] + series[key])

        larger_series = series.toDict()
        larger_series['E'] = 1
        larger_series = Series(larger_series)
        larger_added = self.frame + larger_series

        for key, s in self.frame.iteritems():
            assert_series_equal(larger_added[key], s + series[key])
        self.assert_('E' in larger_added)
        self.assert_(np.isnan(larger_added['E']).all())

        # TimeSeries
        ts = self.tsframe['A']
        added = self.tsframe + ts

        for key, col in self.tsframe.iteritems():
            assert_series_equal(added[key], col + ts)

        smaller_frame = self.tsframe[:-5]
        smaller_added = smaller_frame + ts

        self.assert_(smaller_added.index.equals(self.tsframe.index))

        smaller_ts = ts[:-5]
        smaller_added2 = self.tsframe + smaller_ts
        assert_frame_equal(smaller_added, smaller_added2)

        # length 0
        result = self.tsframe + ts[:0]

        # Frame is length 0
        result = self.tsframe[:0] + ts
        self.assertEqual(len(result), 0)

        # empty but with non-empty index
        frame = self.tsframe[:1].reindex(columns=[])
        result = frame * ts
        self.assertEqual(len(result), len(ts))

    def test_combineFunc(self):
        result = self.frame * 2
        self.assert_(np.array_equal(result.values, self.frame.values * 2))

        result = self.empty * 2
        self.assert_(result.index is self.empty.index)
        self.assertEqual(len(result.columns), 0)

    def test_comparisons(self):
        df1 = tm.makeTimeDataFrame()
        df2 = tm.makeTimeDataFrame()

        row = self.simple.xs('a')

        def test_comp(func):
            result = func(df1, df2)
            self.assert_(np.array_equal(result.values,
                                        func(df1.values, df2.values)))

            result2 = func(self.simple, row)
            self.assert_(np.array_equal(result2.values,
                                        func(self.simple.values, row)))

            result3 = func(self.frame, 0)
            self.assert_(np.array_equal(result3.values,
                                        func(self.frame.values, 0)))

            self.assertRaises(Exception, func, self.simple, self.simple[:2])

        test_comp(operator.eq)
        test_comp(operator.ne)
        test_comp(operator.lt)
        test_comp(operator.gt)
        test_comp(operator.ge)
        test_comp(operator.le)

    def test_toCSV_fromcsv(self):
        path = '__tmp__'

        self.frame['A'][:5] = nan

        self.frame.toCSV(path)
        self.frame.toCSV(path, cols=['A', 'B'])
        self.frame.toCSV(path, header=False)
        self.frame.toCSV(path, index=False)

        # test roundtrip

        self.tsframe.toCSV(path)
        recons = DataFrame.fromcsv(path)

        assert_frame_equal(self.tsframe, recons)

        recons = DataFrame.fromcsv(path, index_col=None)
        assert(len(recons.columns) == len(self.tsframe.columns) + 1)


        # no index
        self.tsframe.toCSV(path, index=False)
        recons = DataFrame.fromcsv(path, index_col=None)
        assert_almost_equal(self.tsframe.values, recons.values)

        # corner case
        dm = DataFrame({'s1' : Series(range(3),range(3)),
                        's2' : Series(range(2),range(2))})
        dm.toCSV(path)
        recons = DataFrame.fromcsv(path)
        assert_frame_equal(dm, recons)

        os.remove(path)

    def test_info(self):
        io = StringIO()
        self.frame.info(buf=io)
        self.tsframe.info(buf=io)

    def test_append(self):
        begin_index = self.frame.index[:5]
        end_index = self.frame.index[5:]

        begin_frame = self.frame.reindex(begin_index)
        end_frame = self.frame.reindex(end_index)

        appended = begin_frame.append(end_frame)
        assert_almost_equal(appended['A'], self.frame['A'])

        del end_frame['A']
        partial_appended = begin_frame.append(end_frame)
        self.assert_('A' in partial_appended)

        partial_appended = end_frame.append(begin_frame)
        self.assert_('A' in partial_appended)

        # mixed type handling
        appended = self.mixed_frame[:5].append(self.mixed_frame[5:])
        assert_frame_equal(appended, self.mixed_frame)

        # what to test here
        mixed_appended = self.mixed_frame[:5].append(self.frame[5:])
        mixed_appended2 = self.frame[:5].append(self.mixed_frame[5:])

        # all equal except 'foo' column
        assert_frame_equal(mixed_appended.reindex(columns=['A', 'B', 'C', 'D']),
                           mixed_appended2.reindex(columns=['A', 'B', 'C', 'D']))

        # append empty
        appended = self.frame.append(self.empty)
        assert_frame_equal(self.frame, appended)
        self.assert_(appended is not self.frame)

        appended = self.empty.append(self.frame)
        assert_frame_equal(self.frame, appended)
        self.assert_(appended is not self.frame)

    def test_asfreq(self):
        offset_monthly = self.tsframe.asfreq(datetools.bmonthEnd)
        rule_monthly = self.tsframe.asfreq('EOM')

        assert_almost_equal(offset_monthly['A'], rule_monthly['A'])

        filled = rule_monthly.asfreq('WEEKDAY', method='pad')
        # TODO: actually check that this worked.

        # don't forget!
        filled_dep = rule_monthly.asfreq('WEEKDAY', method='pad')

        # test does not blow up on length-0 DataFrame
        zero_length = self.tsframe.reindex([])
        result = zero_length.asfreq('EOM')
        self.assert_(result is not zero_length)

    def test_as_matrix(self):
        frame = self.frame
        mat = frame.as_matrix()
        smallerCols = ['C', 'A']

        frameCols = frame.columns
        for i, row in enumerate(mat):
            for j, value in enumerate(row):
                col = frameCols[j]
                if np.isnan(value):
                    self.assert_(np.isnan(frame[col][i]))
                else:
                    self.assertEqual(value, frame[col][i])

        # mixed type
        mat = self.mixed_frame.as_matrix(['foo', 'A'])
        self.assertEqual(mat[0, 0], 'bar')

        # single block corner case
        mat = self.frame.as_matrix(['A', 'B'])
        expected = self.frame.reindex(columns=['A', 'B']).values
        assert_almost_equal(mat, expected)

    def test_values(self):
        self.frame.values[:, 0] = 5.
        self.assert_((self.frame.values[:, 0] == 5).all())

    def test_deepcopy(self):
        cp = deepcopy(self.frame)
        series = cp['A']
        series[:] = 10
        for idx, value in series.iteritems():
            self.assertNotEqual(self.frame['A'][idx], value)

    def test_copy(self):
        cop = self.frame.copy()
        cop['E'] = cop['A']
        self.assert_('E' not in self.frame)

        # copy objects
        copy = self.mixed_frame.copy()
        self.assert_(copy._data is not self.mixed_frame._data)

    def test_corr(self):
        self.frame['A'][:5] = nan
        self.frame['B'][:10] = nan

        correls = self.frame.corr()

        assert_almost_equal(correls['A']['C'],
                            self.frame['A'].corr(self.frame['C']))

    def test_corrwith(self):
        a = self.tsframe
        noise = Series(randn(len(a)), index=a.index)

        b = self.tsframe + noise

        # make sure order does not matter
        b = b.reindex(columns=b.columns[::-1], index=b.index[::-1][10:])
        del b['B']

        colcorr = a.corrwith(b, axis=0)
        assert_almost_equal(colcorr['A'], a['A'].corr(b['A']))

        rowcorr = a.corrwith(b, axis=1)
        assert_series_equal(rowcorr, a.T.corrwith(b.T, axis=0))

        dropped = a.corrwith(b, axis=0, drop=True)
        assert_almost_equal(dropped['A'], a['A'].corr(b['A']))
        self.assert_('B' not in dropped)

        dropped = a.corrwith(b, axis=1, drop=True)
        self.assert_(a.index[-1] not in dropped.index)

    def test_dropEmptyRows(self):
        N = len(self.frame.index)
        mat = randn(N)
        mat[:5] = nan

        frame = DataFrame({'foo' : mat}, index=self.frame.index)

        smaller_frame = frame.dropna(how='all')
        self.assert_(np.array_equal(smaller_frame['foo'], mat[5:]))

        smaller_frame = frame.dropna(how='all', subset=['foo'])
        self.assert_(np.array_equal(smaller_frame['foo'], mat[5:]))

    def test_dropIncompleteRows(self):
        N = len(self.frame.index)
        mat = randn(N)
        mat[:5] = nan

        frame = DataFrame({'foo' : mat}, index=self.frame.index)
        frame['bar'] = 5

        smaller_frame = frame.dropna()
        self.assert_(np.array_equal(smaller_frame['foo'], mat[5:]))

        samesize_frame = frame.dropna(subset=['bar'])
        self.assert_(samesize_frame.index.equals(self.frame.index))

    def test_dropna(self):
        df = DataFrame(np.random.randn(6, 4))
        df[2][:2] = nan

        dropped = df.dropna(axis=1)
        expected = df.ix[:, [0, 1, 3]]
        assert_frame_equal(dropped, expected)

        dropped = df.dropna(axis=0)
        expected = df.ix[range(2, 6)]
        assert_frame_equal(dropped, expected)

        # threshold
        dropped = df.dropna(axis=1, thresh=5)
        expected = df.ix[:, [0, 1, 3]]
        assert_frame_equal(dropped, expected)

        dropped = df.dropna(axis=0, thresh=4)
        expected = df.ix[range(2, 6)]
        assert_frame_equal(dropped, expected)

        dropped = df.dropna(axis=1, thresh=4)
        assert_frame_equal(dropped, df)

        dropped = df.dropna(axis=1, thresh=3)
        assert_frame_equal(dropped, df)

        # subset
        dropped = df.dropna(axis=0, subset=[0, 1, 3])
        assert_frame_equal(dropped, df)

        # all
        dropped = df.dropna(axis=1, how='all')
        assert_frame_equal(dropped, df)

        df[2] = nan
        dropped = df.dropna(axis=1, how='all')
        expected = df.ix[:, [0, 1, 3]]
        assert_frame_equal(dropped, expected)

    def test_dropna_corner(self):
        # bad input
        self.assertRaises(ValueError, self.frame.dropna, how='foo')
        self.assertRaises(ValueError, self.frame.dropna, how=None)

    def test_fillna(self):
        self.tsframe['A'][:5] = nan
        self.tsframe['A'][-5:] = nan

        zero_filled = self.tsframe.fillna(0)
        self.assert_((zero_filled['A'][:5] == 0).all())

        padded = self.tsframe.fillna(method='pad')
        self.assert_(np.isnan(padded['A'][:5]).all())
        self.assert_((padded['A'][-5:] == padded['A'][-5]).all())

        # mixed type
        self.mixed_frame['foo'][5:20] = nan
        self.mixed_frame['A'][-10:] = nan

        result = self.mixed_frame.fillna(value=0)

    def test_truncate(self):
        offset = datetools.bday

        ts = self.tsframe[::3]

        start, end = self.tsframe.index[3], self.tsframe.index[6]

        start_missing = self.tsframe.index[2]
        end_missing = self.tsframe.index[7]

        # neither specified
        truncated = ts.truncate()
        assert_frame_equal(truncated, ts)

        # both specified
        expected = ts[1:3]

        truncated = ts.truncate(start, end)
        assert_frame_equal(truncated, expected)

        truncated = ts.truncate(start_missing, end_missing)
        assert_frame_equal(truncated, expected)

        # start specified
        expected = ts[1:]

        truncated = ts.truncate(before=start)
        assert_frame_equal(truncated, expected)

        truncated = ts.truncate(before=start_missing)
        assert_frame_equal(truncated, expected)

        # end specified
        expected = ts[:3]

        truncated = ts.truncate(after=end)
        assert_frame_equal(truncated, expected)

        truncated = ts.truncate(after=end_missing)
        assert_frame_equal(truncated, expected)

    def test_truncate_copy(self):
        index = self.tsframe.index
        truncated = self.tsframe.truncate(index[5], index[10])
        truncated.values[:] = 5.
        self.assert_(not (self.tsframe.values[5:11] == 5).any())

    def test_xs(self):
        idx = self.frame.index[5]
        xs = self.frame.xs(idx)
        for item, value in xs.iteritems():
            if np.isnan(value):
                self.assert_(np.isnan(self.frame[item][idx]))
            else:
                self.assertEqual(value, self.frame[item][idx])

        # mixed-type xs
        test_data = {
                'A' : {'1' : 1, '2' : 2},
                'B' : {'1' : '1', '2' : '2', '3' : '3'},
        }
        frame = DataFrame(test_data)
        xs = frame.xs('1')
        self.assert_(xs.dtype == np.object_)
        self.assertEqual(xs['A'], 1)
        self.assertEqual(xs['B'], '1')

        self.assertRaises(Exception, self.tsframe.xs,
                          self.tsframe.index[0] - datetools.bday)

    def test_xs_corner(self):
        # pathological mixed-type reordering case
        df = DataFrame(index=[0])
        df['A'] = 1.
        df['B'] = 'foo'
        df['C'] = 2.
        df['D'] = 'bar'
        df['E'] = 3.

        xs = df.xs(0)
        assert_almost_equal(xs, [1., 'foo', 2., 'bar', 3.])

        # no columns but index
        df = DataFrame(index=['a', 'b', 'c'])
        result = df.xs('a')
        expected = Series([])
        assert_series_equal(result, expected)

    def test_pivot(self):
        data = {
            'index' : ['A', 'B', 'C', 'C', 'B', 'A'],
            'columns' : ['One', 'One', 'One', 'Two', 'Two', 'Two'],
            'values' : [1., 2., 3., 3., 2., 1.]
        }

        frame = DataFrame(data)
        pivoted = frame.pivot(index='index', columns='columns', values='values')

        expected = DataFrame({
            'One' : {'A' : 1., 'B' : 2., 'C' : 3.},
            'Two' : {'A' : 1., 'B' : 2., 'C' : 3.}
        })

        assert_frame_equal(pivoted, expected)

        # pivot multiple columns
        wp = tm.makeWidePanel()
        lp = wp.to_long()
        df = DataFrame.from_records(lp.toRecords())
        tm.assert_panel_equal(df.pivot('major', 'minor'), wp)

    def test_reindex(self):
        newFrame = self.frame.reindex(self.ts1.index)

        for col in newFrame.columns:
            for idx, val in newFrame[col].iteritems():
                if idx in self.frame.index:
                    if np.isnan(val):
                        self.assert_(np.isnan(self.frame[col][idx]))
                    else:
                        self.assertEqual(val, self.frame[col][idx])
                else:
                    self.assert_(np.isnan(val))

        for col, series in newFrame.iteritems():
            self.assert_(tm.equalContents(series.index, newFrame.index))
        emptyFrame = self.frame.reindex(Index([]))
        self.assert_(len(emptyFrame.index) == 0)

        # Cython code should be unit-tested directly
        nonContigFrame = self.frame.reindex(self.ts1.index[::2])

        for col in nonContigFrame.columns:
            for idx, val in nonContigFrame[col].iteritems():
                if idx in self.frame.index:
                    if np.isnan(val):
                        self.assert_(np.isnan(self.frame[col][idx]))
                    else:
                        self.assertEqual(val, self.frame[col][idx])
                else:
                    self.assert_(np.isnan(val))

        for col, series in nonContigFrame.iteritems():
            self.assert_(tm.equalContents(series.index,
                                              nonContigFrame.index))

        # corner cases

        # Same index, copies values
        newFrame = self.frame.reindex(self.frame.index)
        self.assert_(newFrame.index is self.frame.index)

        # length zero
        newFrame = self.frame.reindex([])
        self.assert_(not newFrame)
        self.assertEqual(len(newFrame.columns), len(self.frame.columns))

        # length zero with columns reindexed with non-empty index
        newFrame = self.frame.reindex([])
        newFrame = newFrame.reindex(self.frame.index)
        self.assertEqual(len(newFrame.index), len(self.frame.index))
        self.assertEqual(len(newFrame.columns), len(self.frame.columns))

        # pass non-Index
        newFrame = self.frame.reindex(list(self.ts1.index))
        self.assert_(newFrame.index.equals(self.ts1.index))

    def test_reindex_int(self):
        smaller = self.intframe.reindex(self.intframe.index[::2])

        self.assert_(smaller['A'].dtype == np.int_)

        bigger = smaller.reindex(self.intframe.index)
        self.assert_(bigger['A'].dtype == np.float_)

        smaller = self.intframe.reindex(columns=['A', 'B'])
        self.assert_(smaller['A'].dtype == np.int_)

    def test_reindex_like(self):
        other = self.frame.reindex(index=self.frame.index[:10],
                                   columns=['C', 'B'])

        assert_frame_equal(other, self.frame.reindex_like(other))

    def test_reindex_columns(self):
        newFrame = self.frame.reindex(columns=['A', 'B', 'E'])

        assert_series_equal(newFrame['B'], self.frame['B'])
        self.assert_(np.isnan(newFrame['E']).all())
        self.assert_('C' not in newFrame)

        # length zero
        newFrame = self.frame.reindex(columns=[])
        self.assert_(not newFrame)

    def test_reindex_mixed(self):
        pass

    #----------------------------------------------------------------------
    # Transposing

    def test_transpose(self):
        frame = self.frame
        dft = frame.T
        for idx, series in dft.iteritems():
            for col, value in series.iteritems():
                if np.isnan(value):
                    self.assert_(np.isnan(frame[col][idx]))
                else:
                    self.assertEqual(value, frame[col][idx])

        # mixed type
        index, data = tm.getMixedTypeDict()
        mixed = DataFrame(data, index=index)

        mixed_T = mixed.T
        for col, s in mixed_T.iteritems():
            self.assert_(s.dtype == np.object_)

    def test_transpose_get_view(self):
        dft = self.frame.T
        dft.values[:, 5:10] = 5

        self.assert_((self.frame.values[5:10] == 5).all())

    #----------------------------------------------------------------------
    # Renaming

    def test_rename(self):
        mapping = {
            'A' : 'a',
            'B' : 'b',
            'C' : 'c',
            'D' : 'd'
        }
        bad_mapping = {
            'A' : 'a',
            'B' : 'b',
            'C' : 'b',
            'D' : 'd'
        }

        renamed = self.frame.rename(columns=mapping)
        renamed2 = self.frame.rename(columns=str.lower)

        assert_frame_equal(renamed, renamed2)
        assert_frame_equal(renamed2.rename(columns=str.upper),
                           self.frame)

        self.assertRaises(Exception, self.frame.rename,
                          columns=bad_mapping)

        # index

        data = {
            'A' : {'foo' : 0, 'bar' : 1}
        }

        # gets sorted alphabetical
        df = DataFrame(data)
        renamed = df.rename(index={'foo' : 'bar', 'bar' : 'foo'})
        self.assert_(np.array_equal(renamed.index, ['foo', 'bar']))

        renamed = df.rename(index=str.upper)
        self.assert_(np.array_equal(renamed.index, ['BAR', 'FOO']))

        # have to pass something
        self.assertRaises(Exception, self.frame.rename)

    #----------------------------------------------------------------------
    # Time series related

    def test_diff(self):
        the_diff = self.tsframe.diff(1)

        assert_series_equal(the_diff['A'],
                            self.tsframe['A'] - self.tsframe['A'].shift(1))

    def test_shift(self):
        # naive shift
        shiftedFrame = self.tsframe.shift(5)
        self.assert_(shiftedFrame.index.equals(self.tsframe.index))

        shiftedSeries = self.tsframe['A'].shift(5)
        assert_series_equal(shiftedFrame['A'], shiftedSeries)

        shiftedFrame = self.tsframe.shift(-5)
        self.assert_(shiftedFrame.index.equals(self.tsframe.index))

        shiftedSeries = self.tsframe['A'].shift(-5)
        assert_series_equal(shiftedFrame['A'], shiftedSeries)

        # shift by 0
        unshifted = self.tsframe.shift(0)
        assert_frame_equal(unshifted, self.tsframe)

        # shift by DateOffset
        shiftedFrame = self.tsframe.shift(5, offset=datetools.BDay())
        self.assert_(len(shiftedFrame) == len(self.tsframe))

        shiftedFrame2 = self.tsframe.shift(5, timeRule='WEEKDAY')
        assert_frame_equal(shiftedFrame, shiftedFrame2)

        d = self.tsframe.index[0]
        shifted_d = d + datetools.BDay(5)
        assert_series_equal(self.tsframe.xs(d),
                            shiftedFrame.xs(shifted_d))

        # shift int frame
        int_shifted = self.intframe.shift(1)

    def test_apply(self):
        # ufunc
        applied = self.frame.apply(np.sqrt)
        assert_series_equal(np.sqrt(self.frame['A']), applied['A'])

        # aggregator
        applied = self.frame.apply(np.mean)
        self.assertEqual(applied['A'], np.mean(self.frame['A']))

        d = self.frame.index[0]
        applied = self.frame.apply(np.mean, axis=1)
        self.assertEqual(applied[d], np.mean(self.frame.xs(d)))
        self.assert_(applied.index is self.frame.index) # want this

        # empty
        applied = self.empty.apply(np.sqrt)
        self.assert_(not applied)

        applied = self.empty.apply(np.mean)
        self.assert_(not applied)


    def test_apply_broadcast(self):
        broadcasted = self.frame.apply(np.mean, broadcast=True)
        agged = self.frame.apply(np.mean)

        for col, ts in broadcasted.iteritems():
            self.assert_((ts == agged[col]).all())

        broadcasted = self.frame.apply(np.mean, axis=1, broadcast=True)
        agged = self.frame.apply(np.mean, axis=1)
        for idx in broadcasted.index:
            self.assert_((broadcasted.xs(idx) == agged[idx]).all())

    def test_tapply(self):
        d = self.frame.index[0]
        tapplied = self.frame.tapply(np.mean)
        self.assertEqual(tapplied[d], np.mean(self.frame.xs(d)))

    def test_applymap(self):
        applied = self.frame.applymap(lambda x: x * 2)
        assert_frame_equal(applied, self.frame * 2)

        result = self.frame.applymap(type)

    def test_filter(self):
        # items

        filtered = self.frame.filter(['A', 'B', 'E'])
        self.assertEqual(len(filtered.columns), 2)
        self.assert_('E' not in filtered)

        # like
        fcopy = self.frame.copy()
        fcopy['AA'] = 1

        filtered = fcopy.filter(like='A')
        self.assertEqual(len(filtered.columns), 2)
        self.assert_('AA' in filtered)

        # regex
        filtered = fcopy.filter(regex='[A]+')
        self.assertEqual(len(filtered.columns), 2)
        self.assert_('AA' in filtered)

        # pass in None
        self.assertRaises(Exception, self.frame.filter, items=None)

        # objects
        filtered = self.mixed_frame.filter(like='foo')
        self.assert_('foo' in filtered)

    def test_filter_corner(self):
        empty = DataFrame()

        result = empty.filter([])
        assert_frame_equal(result, empty)

        result = empty.filter(like='foo')
        assert_frame_equal(result, empty)

    def test_select(self):
        f = lambda x: x.weekday() == 2
        result = self.tsframe.select(f, axis=0)
        expected = self.tsframe.reindex(
            index=self.tsframe.index[[f(x) for x in self.tsframe.index]])
        assert_frame_equal(result, expected)

        result = self.frame.select(lambda x: x in ('B', 'D'), axis=1)
        expected = self.frame.reindex(columns=['B', 'D'])
        assert_frame_equal(result, expected)

    def test_sort(self):
        # what to test?
        sorted = self.frame.sort()
        sorted_A = self.frame.sort(column='A')

        sorted = self.frame.sort(ascending=False)
        sorted_A = self.frame.sort(column='A', ascending=False)

    def test_combineFirst(self):
        # disjoint
        head, tail = self.frame[:5], self.frame[5:]

        combined = head.combineFirst(tail)
        reordered_frame = self.frame.reindex(combined.index)
        assert_frame_equal(combined, reordered_frame)
        self.assert_(tm.equalContents(combined.columns, self.frame.columns))
        assert_series_equal(combined['A'], reordered_frame['A'])

        # same index
        fcopy = self.frame.copy()
        fcopy['A'] = 1
        del fcopy['C']

        fcopy2 = self.frame.copy()
        fcopy2['B'] = 0
        del fcopy2['D']

        combined = fcopy.combineFirst(fcopy2)

        self.assert_((combined['A'] == 1).all())
        assert_series_equal(combined['B'], fcopy['B'])
        assert_series_equal(combined['C'], fcopy2['C'])
        assert_series_equal(combined['D'], fcopy['D'])

        # overlap
        head, tail = reordered_frame[:10].copy(), reordered_frame
        head['A'] = 1

        combined = head.combineFirst(tail)
        self.assert_((combined['A'][:10] == 1).all())

        # reverse overlap
        tail['A'][:10] = 0
        combined = tail.combineFirst(head)
        self.assert_((combined['A'][:10] == 0).all())

        # no overlap
        f = self.frame[:10]
        g = self.frame[10:]
        combined = f.combineFirst(g)
        assert_series_equal(combined['A'].reindex(f.index), f['A'])
        assert_series_equal(combined['A'].reindex(g.index), g['A'])

        # corner cases
        comb = self.frame.combineFirst(self.empty)
        assert_frame_equal(comb, self.frame)

        comb = self.empty.combineFirst(self.frame)
        assert_frame_equal(comb, self.frame)

    def test_combineFirst_mixed_bug(self):
	idx = Index(['a','b','c','e'])
	ser1 = Series([5.0,-9.0,4.0,100.],index=idx)
	ser2 = Series(['a', 'b', 'c', 'e'], index=idx)
	ser3 = Series([12,4,5,97], index=idx)

	frame1 = DataFrame({"col0" : ser1,
                            "col2" : ser2,
                            "col3" : ser3})

	idx = Index(['a','b','c','f'])
	ser1 = Series([5.0,-9.0,4.0,100.], index=idx)
	ser2 = Series(['a','b','c','f'], index=idx)
	ser3 = Series([12,4,5,97],index=idx)

	frame2 = DataFrame({"col1" : ser1,
                             "col2" : ser2,
                             "col5" : ser3})


        combined = frame1.combineFirst(frame2)
        self.assertEqual(len(combined.columns), 5)

    def test_combineAdd(self):
        # trivial
        comb = self.frame.combineAdd(self.frame)
        assert_frame_equal(comb, self.frame * 2)

        # more rigorous
        a = DataFrame([[1., nan, nan, 2., nan]],
                      columns=np.arange(5))
        b = DataFrame([[2., 3., nan, 2., 6., nan]],
                      columns=np.arange(6))
        expected = DataFrame([[3., 3., nan, 4., 6., nan]],
                             columns=np.arange(6))

        result = a.combineAdd(b)
        assert_frame_equal(result, expected)
        result2 = a.T.combineAdd(b.T)
        assert_frame_equal(result2, expected.T)

        expected2 = a.combine(b, operator.add, fill_value=0.)
        assert_frame_equal(expected, expected2)

        # corner cases
        comb = self.frame.combineAdd(self.empty)
        assert_frame_equal(comb, self.frame)

        comb = self.empty.combineAdd(self.frame)
        assert_frame_equal(comb, self.frame)

        # integer corner case
        df1 = DataFrame({'x':[5]})
        df2 = DataFrame({'x':[1]})
        df3 = DataFrame({'x':[6]})
        comb = df1.combineAdd(df2)
        assert_frame_equal(comb, df3)

        # TODO: test integer fill corner?

    def test_combineMult(self):
        # trivial
        comb = self.frame.combineMult(self.frame)

        assert_frame_equal(comb, self.frame ** 2)

        # corner cases
        comb = self.frame.combineMult(self.empty)
        assert_frame_equal(comb, self.frame)

        comb = self.empty.combineMult(self.frame)
        assert_frame_equal(comb, self.frame)

    def test_join_index(self):
        # left / right

        f = self.frame.reindex(columns=['A', 'B'])[:10]
        f2 = self.frame.reindex(columns=['C', 'D'])

        joined = f.join(f2)
        self.assert_(f.index.equals(joined.index))
        self.assertEqual(len(joined.columns), 4)

        joined = f.join(f2, how='left')
        self.assert_(joined.index.equals(f.index))
        self.assertEqual(len(joined.columns), 4)

        joined = f.join(f2, how='right')
        self.assert_(joined.index.equals(f2.index))
        self.assertEqual(len(joined.columns), 4)

        # corner case
        self.assertRaises(Exception, self.frame.join, self.frame,
                          how='left')

        # inner

        f = self.frame.reindex(columns=['A', 'B'])[:10]
        f2 = self.frame.reindex(columns=['C', 'D'])

        joined = f.join(f2, how='inner')
        self.assert_(joined.index.equals(f.index.intersection(f2.index)))
        self.assertEqual(len(joined.columns), 4)

        # corner case
        self.assertRaises(Exception, self.frame.join, self.frame,
                          how='inner')

        # outer

        f = self.frame.reindex(columns=['A', 'B'])[:10]
        f2 = self.frame.reindex(columns=['C', 'D'])

        joined = f.join(f2, how='outer')
        self.assert_(tm.equalContents(self.frame.index, joined.index))
        self.assertEqual(len(joined.columns), 4)

        # corner case
        self.assertRaises(Exception, self.frame.join, self.frame,
                          how='outer')

        self.assertRaises(Exception, f.join, f2, how='foo')

    def test_join(self):
        index, data = tm.getMixedTypeDict()
        target = DataFrame(data, index=index)

        # Join on string value
        source = DataFrame({'MergedA' : data['A'], 'MergedD' : data['D']},
                            index=data['C'])
        merged = target.join(source, on='C')
        self.assert_(np.array_equal(merged['MergedA'], target['A']))
        self.assert_(np.array_equal(merged['MergedD'], target['D']))

        # join with duplicates (fix regression from DataFrame/Matrix merge)
        df = DataFrame({'key' : ['a', 'a', 'b', 'b', 'c']})
        df2 = DataFrame({'value' : [0, 1, 2]}, index=['a', 'b', 'c'])
        joined = df.join(df2, on='key')
        expected = DataFrame({'key' : ['a', 'a', 'b', 'b', 'c'],
                              'value' : [0, 0, 1, 1, 2]})
        assert_frame_equal(joined, expected)

        # Test when some are missing
        df_a = DataFrame([[1], [2], [3]], index=['a', 'b', 'c'],
                         columns=['one'])
        df_b = DataFrame([['foo'], ['bar']], index=[1, 2],
                         columns=['two'])
        df_c = DataFrame([[1], [2]], index=[1, 2],
                         columns=['three'])
        joined = df_a.join(df_b, on='one')
        joined = joined.join(df_c, on='one')
        self.assert_(np.isnan(joined['two']['c']))
        self.assert_(np.isnan(joined['three']['c']))

        # merge column not p resent
        self.assertRaises(Exception, target.join, source, on='E')

        # corner cases

        # nothing to merge
        merged = target.join(source.reindex([]), on='C')

        # overlap
        source_copy = source.copy()
        source_copy['A'] = 0
        self.assertRaises(Exception, target.join, source_copy, on='A')

        # can't specify how
        self.assertRaises(Exception, target.join, source, on='C',
                          how='left')

    def test_clip(self):
        median = self.frame.median().median()

        capped = self.frame.clip_upper(median)
        self.assert_(not (capped.values > median).any())

        floored = self.frame.clip_lower(median)
        self.assert_(not (floored.values < median).any())

        double = self.frame.clip(upper=median, lower=median)
        self.assert_(not (double.values != median).any())

    def test_get_X_columns(self):
        # numeric and object columns

        # Booleans get casted to float in DataFrame, so skip for now
        df = DataFrame({'a' : [1, 2, 3],
                         # 'b' : [True, False, True],
                         'c' : ['foo', 'bar', 'baz'],
                         'd' : [None, None, None],
                         'e' : [3.14, 0.577, 2.773]})

        self.assertEquals(df._get_numeric_columns(), ['a', 'e'])
        # self.assertEquals(df._get_object_columns(), ['c', 'd'])

    def test_statistics(self):
        # unnecessary?
        sumFrame = self.frame.apply(np.sum)
        for col, series in self.frame.iteritems():
            self.assertEqual(sumFrame[col], series.sum())

    def _check_statistic(self, frame, name, alternative):
        f = getattr(frame, name)

        result = f(axis=0)
        assert_series_equal(result, frame.apply(alternative))

        result = f(axis=1)
        comp = frame.apply(alternative, axis=1).reindex(result.index)
        assert_series_equal(result, comp)

        self.assertRaises(Exception, f, axis=2)

    def test_count(self):
        f = lambda s: notnull(s).sum()

        self._check_statistic(self.frame, 'count', f)

        # corner case

        frame = DataFrame()
        ct1 = frame.count(1)
        self.assert_(isinstance(ct1, Series))

        ct2 = frame.count(0)
        self.assert_(isinstance(ct2, Series))

    def test_sum(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].sum()

        self._check_statistic(self.frame, 'sum', f)

        axis0 = self.empty.sum(0)
        axis1 = self.empty.sum(1)
        self.assert_(isinstance(axis0, Series))
        self.assert_(isinstance(axis1, Series))
        self.assertEquals(len(axis0), 0)
        self.assertEquals(len(axis1), 0)

    def test_sum_object(self):
        values = self.frame.values.astype(int)
        frame = DataFrame(values, index=self.frame.index,
                           columns=self.frame.columns)
        deltas = frame * timedelta(1)
        deltas.sum()

    def test_sum_bool(self):
        # ensure this works, bug report
        bools = np.isnan(self.frame)
        bools.sum(1)
        bools.sum(0)

    def test_product(self):
        def f(x):
            x = np.asarray(x)
            return np.prod(x[notnull(x)])

        self._check_statistic(self.frame, 'product', f)

    def test_mean(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].mean()

        self._check_statistic(self.frame, 'mean', f)

        # unit test when have object data
        the_mean = self.mixed_frame.mean(axis=0)
        the_sum = self.mixed_frame.sum(axis=0, numeric_only=True)
        self.assert_(the_sum.index.equals(the_mean.index))
        self.assert_(len(the_mean.index) < len(self.mixed_frame.columns))

        # xs sum mixed type, just want to know it works...
        the_mean = self.mixed_frame.mean(axis=1)
        the_sum = self.mixed_frame.sum(axis=1, numeric_only=True)
        self.assert_(the_sum.index.equals(the_mean.index))

        # take mean of boolean column
        self.frame['bool'] = self.frame['A'] > 0
        means = self.frame.mean(0)
        self.assertEqual(means['bool'], self.frame['bool'].values.mean())

    def test_stats_mixed_type(self):
        # don't blow up
        self.mixed_frame.std(1)
        self.mixed_frame.var(1)
        self.mixed_frame.mean(1)
        self.mixed_frame.skew(1)

    def test_median(self):
        def f(x):
            x = np.asarray(x)
            return np.median(x[notnull(x)])

        self._check_statistic(self.intframe, 'median', f)
        self._check_statistic(self.frame, 'median', f)

    def test_min(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].min()

        self._check_statistic(self.frame, 'min', f)

    def test_max(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].max()

        self._check_statistic(self.frame, 'max', f)

    def test_mad(self):
        f = lambda x: np.abs(x - x.mean()).mean()

        self._check_statistic(self.frame, 'mad', f)

    def test_var(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].var(ddof=1)

        self._check_statistic(self.frame, 'var', f)

    def test_std(self):
        def f(x):
            x = np.asarray(x)
            return x[notnull(x)].std(ddof=1)

        self._check_statistic(self.frame, 'std', f)

    def test_skew(self):
        try:
            from scipy.stats import skew
        except ImportError:
            return

        def f(x):
            x = np.asarray(x)
            return skew(x[notnull(x)], bias=False)

        self._check_statistic(self.frame, 'skew', f)

    def test_quantile(self):
        try:
            from scipy.stats import scoreatpercentile
        except ImportError:
            return

        q = self.tsframe.quantile(0.1, axis=0)
        self.assertEqual(q['A'], scoreatpercentile(self.tsframe['A'], 10))
        q = self.tsframe.quantile(0.9, axis=1)
        q = self.intframe.quantile(0.1)
        self.assertEqual(q['A'], scoreatpercentile(self.intframe['A'], 10))

    def test_cumsum(self):
        self.tsframe.ix[5:10, 0] = nan
        self.tsframe.ix[10:15, 1] = nan
        self.tsframe.ix[15:, 2] = nan

        # axis = 0
        cumsum = self.tsframe.cumsum()
        expected = self.tsframe.apply(Series.cumsum)
        assert_frame_equal(cumsum, expected)

        # axis = 1
        cumsum = self.tsframe.cumsum(axis=1)
        expected = self.tsframe.apply(Series.cumsum, axis=1)
        assert_frame_equal(cumsum, expected)

        # works
        df = DataFrame({'A' : np.arange(20)}, index=np.arange(20))
        result = df.cumsum()

        # fix issue
        cumsum_xs = self.tsframe.cumsum(axis=1)
        self.assertEqual(np.shape(cumsum_xs), np.shape(self.tsframe))


    def test_cumprod(self):
        self.tsframe.ix[5:10, 0] = nan
        self.tsframe.ix[10:15, 1] = nan
        self.tsframe.ix[15:, 2] = nan

        # axis = 0
        cumprod = self.tsframe.cumprod()
        expected = self.tsframe.apply(Series.cumprod)
        assert_frame_equal(cumprod, expected)

        # axis = 1
        cumprod = self.tsframe.cumprod(axis=1)
        expected = self.tsframe.apply(Series.cumprod, axis=1)
        assert_frame_equal(cumprod, expected)

        # fix issue
        cumprod_xs = self.tsframe.cumprod(axis=1)
        self.assertEqual(np.shape(cumprod_xs), np.shape(self.tsframe))

    def test_describe(self):
        desc = self.tsframe.describe()
        desc = self.mixed_frame.describe()
        desc = self.frame.describe()

    def test_get_axis_etc(self):
        f = self.frame

        self.assertEquals(f._get_axis_number(0), 0)
        self.assertEquals(f._get_axis_number(1), 1)
        self.assertEquals(f._get_axis_name(0), 'index')
        self.assertEquals(f._get_axis_name(1), 'columns')

        self.assert_(f._get_axis(0) is f.index)
        self.assert_(f._get_axis(1) is f.columns)
        self.assertRaises(Exception, f._get_axis_number, 2)

    def test_combineFirst_mixed(self):
        a = Series(['a','b'], index=range(2))
        b = Series(range(2), index=range(2))
        f = DataFrame({'A' : a, 'B' : b})

        a = Series(['a','b'], index=range(5, 7))
        b = Series(range(2), index=range(5, 7))
        g = DataFrame({'A' : a, 'B' : b})

        combined = f.combineFirst(g)

    def test_more_asMatrix(self):
        values = self.mixed_frame.as_matrix()
        self.assertEqual(values.shape[1], len(self.mixed_frame.columns))

    def test_reindex_boolean(self):
        frame = DataFrame(np.ones((10, 2), dtype=bool),
                           index=np.arange(0, 20, 2),
                           columns=[0, 2])

        reindexed = frame.reindex(np.arange(10))
        self.assert_(reindexed.values.dtype == np.object_)
        self.assert_(isnull(reindexed[0][1]))

        reindexed = frame.reindex(columns=range(3))
        self.assert_(reindexed.values.dtype == np.object_)
        self.assert_(isnull(reindexed[1]).all())

    def test_reindex_objects(self):
        reindexed = self.mixed_frame.reindex(columns=['foo', 'A', 'B'])
        self.assert_('foo' in reindexed)

        reindexed = self.mixed_frame.reindex(columns=['A', 'B'])
        self.assert_('foo' not in reindexed)

    def test_reindex_corner(self):
        index = Index(['a', 'b', 'c'])
        dm = self.empty.reindex(index=[1, 2, 3])
        reindexed = dm.reindex(columns=index)
        self.assert_(reindexed.columns.equals(index))

        # ints are weird

        smaller = self.intframe.reindex(columns=['A', 'B', 'E'])
        self.assert_(smaller['E'].dtype == np.float_)

    def test_rename_objects(self):
        renamed = self.mixed_frame.rename(columns=str.upper)
        self.assert_('FOO' in renamed)
        self.assert_('foo' not in renamed)

    def test_fill_corner(self):
        self.mixed_frame['foo'][5:20] = nan
        self.mixed_frame['A'][-10:] = nan

        filled = self.mixed_frame.fillna(value=0)
        self.assert_((filled['foo'][5:20] == 0).all())
        del self.mixed_frame['foo']

        empty_float = self.frame.reindex(columns=[])
        result = empty_float.fillna(value=0)

    def test_count_objects(self):
        dm = DataFrame(self.mixed_frame._series)
        df = DataFrame(self.mixed_frame._series)

        tm.assert_series_equal(dm.count(), df.count())
        tm.assert_series_equal(dm.count(1), df.count(1))

    def test_cumsum_corner(self):
        dm = DataFrame(np.arange(20).reshape(4, 5),
                        index=range(4), columns=range(5))
        result = dm.cumsum()

    #----------------------------------------------------------------------
    # Stacking / unstacking

    def test_stack_unstack(self):
        stacked = self.frame.stack()
        stacked_df = DataFrame({'foo' : stacked, 'bar' : stacked})

        unstacked = stacked.unstack()
        unstacked_df = stacked_df.unstack()

        assert_frame_equal(unstacked, self.frame)
        assert_frame_equal(unstacked_df['bar'], self.frame)

        unstacked_cols = stacked.unstack(0)
        unstacked_cols_df = stacked_df.unstack(0)
        assert_frame_equal(unstacked_cols.T, self.frame)
        assert_frame_equal(unstacked_cols_df['bar'].T, self.frame)

    def test_delevel(self):
        stacked = self.frame.stack()[::2]
        stacked = DataFrame({'foo' : stacked, 'bar' : stacked})
        deleveled = stacked.delevel()

        for i, (lev, lab) in enumerate(zip(stacked.index.levels,
                                           stacked.index.labels)):
            values = lev.take(lab)
            assert_almost_equal(values, deleveled['label_%d' % i])

        self.assertRaises(Exception, self.frame.delevel)

    #----------------------------------------------------------------------
    # Tests to cope with refactored internals

    def test_as_matrix_numeric_cols(self):
        self.frame['foo'] = 'bar'

        values = self.frame.as_matrix(['A', 'B', 'C', 'D'])
        self.assert_(values.dtype == np.float64)

    def test_constructor_frame_copy(self):
        cop = DataFrame(self.frame, copy=True)
        cop['A'] = 5
        self.assert_((cop['A'] == 5).all())
        self.assert_(not (self.frame['A'] == 5).all())

    def test_constructor_ndarray_copy(self):
        df = DataFrame(self.frame.values)

        self.frame.values[5] = 5
        self.assert_((df.values[5] == 5).all())

        df = DataFrame(self.frame.values, copy=True)
        self.frame.values[6] = 6
        self.assert_(not (df.values[6] == 6).all())

    def test_constructor_series_copy(self):
        series = self.frame._series

        df = DataFrame({'A' : series['A']})
        df['A'][:] = 5

        self.assert_(not (series['A'] == 5).all())

    def test_assign_columns(self):
        self.frame['hi'] = 'there'

        frame = self.frame.copy()
        frame.columns = ['foo', 'bar', 'baz', 'quux', 'foo2']
        assert_series_equal(self.frame['C'], frame['baz'])
        assert_series_equal(self.frame['hi'], frame['foo2'])

    def test_cast_internals(self):
        casted = DataFrame(self.frame._data, dtype=int)
        expected = DataFrame(self.frame._series, dtype=int)
        assert_frame_equal(casted, expected)

    def test_consolidate(self):
        self.frame['E'] = 7.
        consolidated = self.frame.consolidate()
        self.assert_(len(consolidated._data.blocks) == 1)

        # Ensure copy, do I want this?
        recons = consolidated.consolidate()
        self.assert_(recons is not consolidated)
        assert_frame_equal(recons, consolidated)

    def test_as_matrix_consolidate(self):
        self.frame['E'] = 7.
        self.assert_(not self.frame._data.is_consolidated())
        _ = self.frame.as_matrix()
        self.assert_(self.frame._data.is_consolidated())

    def test_modify_values(self):
        self.frame.values[5] = 5
        self.assert_((self.frame.values[5] == 5).all())

        # unconsolidated
        self.frame['E'] = 7.
        self.frame.values[6] = 6
        self.assert_((self.frame.values[6] == 6).all())

    def test_boolean_set_uncons(self):
        self.frame['E'] = 7.

        expected = self.frame.values.copy()
        expected[expected > 1] = 2

        self.frame[self.frame > 1] = 2
        assert_almost_equal(expected, self.frame.values)

    def test_boolean_set_mixed_type(self):
        bools = self.mixed_frame.applymap(lambda x: x != 2).astype(bool)
        self.assertRaises(Exception, self.mixed_frame.__setitem__, bools, 2)

    def test_xs_view(self):
        dm = DataFrame(np.arange(20.).reshape(4, 5),
                       index=range(4), columns=range(5))

        dm.xs(2, copy=False)[:] = 5
        self.assert_((dm.xs(2) == 5).all())

        dm.xs(2)[:] = 10
        self.assert_((dm.xs(2) == 5).all())

        # TODO (?): deal with mixed-type fiasco?
        self.assertRaises(Exception, self.mixed_frame.xs,
                          self.mixed_frame.index[2], copy=False)

        # unconsolidated
        dm['foo'] = 6.
        dm.xs(3, copy=False)[:] = 10
        self.assert_((dm.xs(3) == 10).all())

    def test_boolean_indexing(self):
        idx = range(3)
        cols = range(3)
        df1 = DataFrame(index=idx, columns=cols, \
                           data=np.array([[0.0, 0.5, 1.0],
                                          [1.5, 2.0, 2.5],
                                          [3.0, 3.5, 4.0]], dtype=float))
        df2 = DataFrame(index=idx, columns=cols, data=np.ones((len(idx), len(cols))))

        expected = DataFrame(index=idx, columns=cols, \
                           data=np.array([[0.0, 0.5, 1.0],
                                          [1.5, 2.0, -1],
                                          [-1,  -1,  -1]], dtype=float))

        df1[df1 > 2.0 * df2] = -1
        assert_frame_equal(df1, expected)

    def test_sum_bools(self):
        df = DataFrame(index=range(1), columns=range(10))
        bools = np.isnan(df)
        self.assert_(bools.sum(axis=1)[0] == 10)

    def test_fillna_col_reordering(self):
        idx = range(20)
        cols = ["COL." + str(i) for i in range(5, 0, -1)]
        data = np.random.rand(20, 5)
        df = DataFrame(index=range(20), columns=cols, data=data)
        self.assert_(df.columns.tolist() == df.fillna().columns.tolist())


if __name__ == '__main__':
    # unittest.main()
    import nose
    # nose.runmodule(argv=[__file__,'-vvs','-x', '--pdb-failure'],
    #                exit=False)
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

