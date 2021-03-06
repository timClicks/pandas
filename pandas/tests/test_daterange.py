from datetime import datetime
import pickle
import unittest

import numpy as np

import pandas.core.datetools as datetools
from pandas.core.index import Index
from pandas.core.daterange import DateRange, generate_range
import pandas.core.daterange as daterange

try:
    import pytz
except ImportError:
    pass

def eqXDateRange(kwargs, expected):
    rng = generate_range(**kwargs)
    assert(np.array_equal(list(rng), expected))

START, END = datetime(2009, 1, 1), datetime(2010, 1, 1)

class TestDateRangeGeneration(unittest.TestCase):
    def test_generate(self):
        rng1 = list(generate_range(START, END, offset=datetools.bday))
        rng2 = list(generate_range(START, END, timeRule='WEEKDAY'))
        self.assert_(np.array_equal(rng1, rng2))

    def test_1(self):
        eqXDateRange(dict(start=datetime(2009, 3, 25),
                          periods=2),
                     [datetime(2009, 3, 25), datetime(2009, 3, 26)])

    def test_2(self):
        eqXDateRange(dict(start=datetime(2008, 1, 1),
                          end=datetime(2008, 1, 3)),
                     [datetime(2008, 1, 1),
                      datetime(2008, 1, 2),
                      datetime(2008, 1, 3)])

    def test_3(self):
        eqXDateRange(dict(start = datetime(2008, 1, 5),
                          end = datetime(2008, 1, 6)),
                     [])

class TestDateRange(unittest.TestCase):

    def setUp(self):
        self.rng = DateRange(START, END, offset=datetools.bday)

    def test_constructor(self):
        rng = DateRange(START, END, offset=datetools.bday)
        rng = DateRange(START, periods=20, offset=datetools.bday)
        rng = DateRange(end=START, periods=20, offset=datetools.bday)

    def test_cached_range(self):
        rng = DateRange._cached_range(START, END, offset=datetools.bday)
        rng = DateRange._cached_range(START, periods=20, offset=datetools.bday)
        rng = DateRange._cached_range(end=START, periods=20,
                                       offset=datetools.bday)

        self.assertRaises(Exception, DateRange._cached_range, START, END)

        self.assertRaises(Exception, DateRange._cached_range, START,
                          offset=datetools.bday)

        self.assertRaises(Exception, DateRange._cached_range, end=END,
                          offset=datetools.bday)

        self.assertRaises(Exception, DateRange._cached_range, periods=20,
                          offset=datetools.bday)

    def test_cached_range_bug(self):
        rng = DateRange('2010-09-01 05:00:00', periods=50,
                        offset=datetools.DateOffset(hours=6))
        self.assertEquals(len(rng), 50)
        self.assertEquals(rng[0], datetime(2010, 9, 1, 5))

    def test_comparison(self):
        d = self.rng[10]

        comp = self.rng > d
        self.assert_(comp[11])
        self.assert_(not comp[9])

    def test_repr(self):
        # only really care that it works
        repr(self.rng)

    def test_getitem(self):
        smaller = self.rng[:5]
        self.assert_(np.array_equal(smaller, self.rng.view(np.ndarray)[:5]))
        self.assertEquals(smaller.offset, self.rng.offset)

        sliced = self.rng[::5]
        self.assertEquals(sliced.offset, datetools.bday * 5)

        fancy_indexed = self.rng[[4, 3, 2, 1, 0]]
        self.assertEquals(len(fancy_indexed), 5)
        self.assert_(not isinstance(fancy_indexed, DateRange))

        # 32-bit vs. 64-bit platforms
        self.assertEquals(self.rng[4], self.rng[np.int_(4)])

    def test_shift(self):
        shifted = self.rng.shift(5)
        self.assertEquals(shifted[0], self.rng[5])
        self.assertEquals(shifted.offset, self.rng.offset)

        shifted = self.rng.shift(-5)
        self.assertEquals(shifted[5], self.rng[0])
        self.assertEquals(shifted.offset, self.rng.offset)

        shifted = self.rng.shift(0)
        self.assertEquals(shifted[0], self.rng[0])
        self.assertEquals(shifted.offset, self.rng.offset)

        rng = DateRange(START, END, offset=datetools.bmonthEnd)
        shifted = rng.shift(1, offset=datetools.bday)
        self.assertEquals(shifted[0], rng[0] + datetools.bday)

    def test_pickle_unpickle(self):
        pickled = pickle.dumps(self.rng)
        unpickled = pickle.loads(pickled)

        self.assert_(unpickled.offset is not None)

    def test_union(self):
        # overlapping
        left = self.rng[:10]
        right = self.rng[5:10]

        the_union = left.union(right)
        self.assert_(isinstance(the_union, DateRange))

        # non-overlapping, gap in middle
        left = self.rng[:5]
        right = self.rng[10:]

        the_union = left.union(right)
        self.assert_(isinstance(the_union, Index))
        self.assert_(not isinstance(the_union, DateRange))

        # non-overlapping, no gap
        left = self.rng[:5]
        right = self.rng[5:10]

        the_union = left.union(right)
        self.assert_(isinstance(the_union, DateRange))

        # order does not matter
        self.assert_(np.array_equal(right.union(left), the_union))

        # overlapping, but different offset
        rng = DateRange(START, END, offset=datetools.bmonthEnd)

        the_union = self.rng.union(rng)
        self.assert_(not isinstance(the_union, DateRange))

    def test_with_tzinfo(self):
        _skip_if_no_pytz()
        tz = pytz.timezone('US/Central')

        # just want it to work
        start = datetime(2011, 3, 12, tzinfo=pytz.utc)
        dr = DateRange(start, periods=50, offset=datetools.Hour())
        self.assert_(dr.tzinfo is not None)
        self.assert_(dr.tzinfo is start.tzinfo)

        # DateRange with naive datetimes
        dr = DateRange('1/1/2005', '1/1/2009', tzinfo=pytz.utc)
        dr = DateRange('1/1/2005', '1/1/2009', tzinfo=tz)

        # normalized
        central = dr.tz_normalize(tz)
        self.assert_(central.tzinfo is tz)
        self.assert_(central[0].tzinfo is tz)

        # datetimes with tzinfo set
        dr = DateRange(datetime(2005, 1, 1, tzinfo=pytz.utc),
                       '1/1/2009', tzinfo=pytz.utc)

        self.assertRaises(Exception, DateRange,
                          datetime(2005, 1, 1, tzinfo=pytz.utc),
                          '1/1/2009', tzinfo=tz)

    def test_tz_localize(self):
        _skip_if_no_pytz()
        dr = DateRange('1/1/2009', '1/1/2010')
        dr_utc = DateRange('1/1/2009', '1/1/2010', tzinfo=pytz.utc)
        localized = dr.tz_localize(pytz.utc)
        self.assert_(np.array_equal(dr_utc, localized))

    def test_with_tzinfo_ambiguous_times(self):
        _skip_if_no_pytz()
        tz = pytz.timezone('US/Eastern')

        # regular no problem
        self.assert_(self.rng.tz_validate())

        # March 13, 2011, spring forward, skip from 2 AM to 3 AM
        dr = DateRange(datetime(2011, 3, 13, 1, 30), periods=3,
                       offset=datetools.Hour(), tzinfo=tz)
        self.assert_(not dr.tz_validate())

        # after dst transition
        dr = DateRange(datetime(2011, 3, 13, 3, 30), periods=3,
                       offset=datetools.Hour(), tzinfo=tz)
        self.assert_(dr.tz_validate())

        # November 6, 2011, fall back, repeat 2 AM hour
        dr = DateRange(datetime(2011, 11, 6, 1, 30), periods=3,
                       offset=datetools.Hour(), tzinfo=tz)
        self.assert_(not dr.tz_validate())

        # UTC is OK
        dr = DateRange(datetime(2011, 3, 13), periods=48,
                       offset=datetools.Minute(30), tzinfo=pytz.utc)
        self.assert_(dr.tz_validate())

    def test_summary(self):
        self.rng.summary()
        self.rng[2:2].summary()
        try:
            DateRange('1/1/2005', '1/1/2009', tzinfo=pytz.utc).summary()
        except Exception:
            pass

    def test_misc(self):
        end = datetime(2009, 5, 13)
        dr = DateRange(end=end, periods=20)
        firstDate = end - 19 * datetools.bday

        assert len(dr) == 20
        assert dr[0] == firstDate
        assert dr[-1] == end

    # test utility methods
    def test_infer_tzinfo(self):
        _skip_if_no_pytz()
        eastern = pytz.timezone('US/Eastern')
        utc = pytz.utc

        _start = datetime(2001, 1, 1)
        _end = datetime(2009, 1, 1)

        start = eastern.localize(_start)
        end = eastern.localize(_end)
        assert(daterange._infer_tzinfo(start, end) is eastern)
        assert(daterange._infer_tzinfo(start, None) is eastern)
        assert(daterange._infer_tzinfo(None, end) is eastern)

        start = utc.localize(_start)
        end = utc.localize(_end)
        assert(daterange._infer_tzinfo(start, end) is utc)

        end = eastern.localize(_end)
        self.assertRaises(Exception, daterange._infer_tzinfo, start, end)
        self.assertRaises(Exception, daterange._infer_tzinfo, end, start)

def _skip_if_no_pytz():
    try:
        import pytz
    except ImportError:
        raise nose.SkipTest

if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

