import unittest

from verminator.utils import *


class UtilsCase(unittest.TestCase):

    def setUp(self):
        pass

    def assert_vrange_equal(self, vr, other):
        vr = (parse_version(vr[0]), parse_version(vr[1]))
        other = (parse_version(other[0]), parse_version(other[1]))
        self.assertTrue(vr[0] == other[0] and vr[1] == other[1])

    def test_filter_vrange(self):
        vr = (parse_version('sophonweb-1.3.0-final'), parse_version('sophonweb-2.2.1-final'))
        other = (parse_version('sophonweb-2.2.0-final'), parse_version('sophonweb-2.2.0-final'))
        filtered = filter_vrange(vr, other)
        self.assert_vrange_equal(filtered, other)

        vr = (parse_version('sophonweb-1.3.0-final'), parse_version('sophonweb-1.3.0-final'))
        other = (parse_version('sophonweb-1.3.0-final'), parse_version('sophonweb-1.3.0-final'))
        self.assert_vrange_equal(filter_vrange(vr, other), other)

        vr = (parse_version('sophonweb-2.2.0-final'), parse_version('sophonweb-2.2.0-final'))
        other = (parse_version('sophonweb-1.3.0-final'), parse_version('sophonweb-1.3.0-final'))
        self.assertTrue(filter_vrange(vr, other) is None)

        vr = (parse_version('sophonweb-2.0.0-final'), parse_version('sophonweb-2.0.0-final'))
        other = (parse_version('sophonweb-1.3.0-final'), parse_version('sophonweb-2.2.0-final'))
        self.assert_vrange_equal(filter_vrange(vr, other), vr)

        vr = (parse_version('transwarp-5.2.1-final'), parse_version('transwarp-6.0.2-final'))
        other = (parse_version('transwarp-5.2.1-final'), parse_version('transwarp-5.2.1-final'))
        self.assert_vrange_equal(filter_vrange(vr, other), other)
