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

    def test_parse_version(self):
        v = parse_version('tdc-1.2')
        self.assertTrue(v.maintenance is None and v.build is None and v.suffix_version is None)
        v = parse_version('tdc-1.2.1-final')
        self.assertTrue(v.suffix == 'final' and v.minor == 2 and v.maintenance == 1)

    def test_is_major_version(self):
        self.assertTrue(is_major_version('tdc-1.2'))
        self.assertTrue(not is_major_version('tdc-1.2.1'))
        self.assertTrue(not is_major_version('tdc-1.2.1-final'))

    def test_replace_product_name(self):
        self.assertTrue(str(replace_product_name('tdc-1.2', 'gzes')) == 'gzes-1.2')
        self.assertTrue(str(replace_product_name('transwarp-1.2', 'gzes', by='tdc')) == 'transwarp-1.2')
        self.assertTrue(str(replace_product_name('tdc-1.2', 'gzes', by='tdc')) == 'gzes-1.2')

    def test_concatenate_vranges(self):
        cvr = concatenate_vranges([
            (parse_version('sophonweb-1.2.0-final'), parse_version('sophonweb-2.2.0-final')),
            (parse_version('sophonweb-1.3.0-rc0'), parse_version('sophonweb-1.3.0-rc3'))
        ])
        self.assertTrue(len(cvr) == 1)
        self.assert_vrange_equal(cvr[0], (parse_version('sophonweb-1.2.0-final'), parse_version('sophonweb-2.2.0-final')))

        cvr = concatenate_vranges([
            (parse_version('tdc-1.0.0-rc0'), parse_version('tdc-1.0.0-final')),
            (parse_version('tdc-1.1.0-rc0'), parse_version('tdc-1.1.0-final')),
            (parse_version('tdc-1.2.0-rc0'), parse_version('tdc-1.2.0-final')),
        ])
        self.assertTrue(len(cvr) == 1)
        self.assert_vrange_equal(cvr[0], (parse_version('tdc-1.0.0-rc0'), parse_version('tdc-1.2.0-final')))

        cvr = concatenate_vranges([
            (parse_version('tdc-1.0.0-rc0'), parse_version('tdc-1.0.0-final')),
            (parse_version('transwarp-1.1.0-rc0'), parse_version('transwarp-1.1.0-final')),
            (parse_version('tdc-1.2.0-rc0'), parse_version('tdc-1.2.0-final')),
        ])
        self.assertTrue(len(cvr) == 2)
        self.assert_vrange_equal(cvr[0], (parse_version('tdc-1.0.0-rc0'), parse_version('tdc-1.2.0-final')))
        self.assert_vrange_equal(cvr[1], (parse_version('transwarp-1.1.0-rc0'), parse_version('transwarp-1.1.0-final')))