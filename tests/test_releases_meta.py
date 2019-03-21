import unittest
from pathlib import Path

from verminator.releasemeta import ProductReleaseMeta
from verminator.utils import *


class ProductReleaseMetaCase(unittest.TestCase):

    def setUp(self):
        this_file = Path(__file__)
        self.oem_yml = this_file.parent.joinpath('releasesmeta/oem.yml')
        self.tdc_yml = this_file.parent.joinpath('releasesmeta/tdc.yml')
        self.tdc2ex_yml = this_file.parent.joinpath('releasesmeta/tdc2ex.yml')

    def test_official(self):
        meta = ProductReleaseMeta(self.tdc_yml)
        releases = [str(i) for i in meta.major_versioned_releases.keys()]
        self.assertTrue('tdc-1.0' in releases)
        self.assertTrue('tdc-1.1' in releases)
        self.assertTrue('tdc-1.2' in releases)
        self.assertFalse('tdc-1.1.0-final' in releases)

    def test_oem(self):
        meta = ProductReleaseMeta(self.oem_yml)
        releases = [str(i) for i in meta.major_versioned_releases.keys()]
        self.assertTrue('gzes-1.0' in releases)
        self.assertTrue('gzes-1.1' in releases)
        self.assertTrue('gzes-1.2' in releases)
        self.assertFalse('gzes-1.1.0-final' in releases)

    def assert_vrange_equal(self, vr, other):
        vr = (parse_version(vr[0]), parse_version(vr[1]))
        other = (parse_version(other[0]), parse_version(other[1]))
        self.assertTrue(vr[0] == other[0] and vr[1] == other[1])

    def test_get_tdc_version_range_legacy(self):
        meta = ProductReleaseMeta(self.tdc_yml)

        pv = meta.get_compatible_versions('sophonweb-1.3.0-final')
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-1.1.0-rc2', 'tdc-1.2.1-rc1'))
        self.assert_vrange_equal(pv.get('transwarp')[0], ('transwarp-5.2.1-final', 'transwarp-5.2.3-final'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-1.3.0-final', 'sophonweb-1.3.0-final'))

        pv = meta.get_tdc_version_range('sophonweb-1.3.0-final')
        self.assert_vrange_equal(pv, ('tdc-1.1.0-rc2', 'tdc-1.2.1-rc1'))

        pv = meta.get_tdc_version_range('sophonweb-2.1.0-final')
        self.assert_vrange_equal(pv, ('tdc-1.2.0-rc3', 'tdc-1.2.1-rc1'))

        pv = meta.get_tdc_version_range()
        self.assert_vrange_equal(pv, ('tdc-1.0.0-rc1', 'tdc-1.2.1-rc1'))

    def test_get_compatible_versions(self):
        meta = ProductReleaseMeta(self.tdc2ex_yml)
        pv = meta.get_compatible_versions('tdc-2.0.0-rc1')
        self.assert_vrange_equal(pv.get('transwarp')[0], ('transwarp-5.2.1-final', 'transwarp-6.0.1-final'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-1.3.0-final', 'sophonweb-2.2.0-final'))
        self.assert_vrange_equal(pv.get('tos')[0], ('tos-1.9.0-final', 'tos-1.9.1-final'))
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-2.0.0-rc1', 'tdc-2.0.0-rc1'))

        pv = meta.get_compatible_versions('tdc-2.0.0-rc3')
        self.assert_vrange_equal(pv.get('transwarp')[0], ('transwarp-5.2.1-final', 'transwarp-6.0.2-final'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-2.2.0-final', 'sophonweb-2.2.1-final'))
        self.assert_vrange_equal(pv.get('tos')[0], ('tos-1.9.2-final', 'tos-1.9.2-final'))

        pv = meta.get_compatible_versions('sophonweb-2.2.0-final')
        self.assert_vrange_equal(pv.get('transwarp')[0], ('transwarp-5.2.1-final', 'transwarp-5.2.3-final'))
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc3'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-2.2.0-final', 'sophonweb-2.2.0-final'))

        pv = meta.get_compatible_versions('transwarp-5.2.1-final')
        self.assert_vrange_equal(pv.get('transwarp')[0], ('transwarp-5.2.1-final', 'transwarp-5.2.1-final'))
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc3'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-1.3.0-final', 'sophonweb-2.2.1-final'))

        pv = meta.get_compatible_versions('transwarp-6.0.1-final')
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc3'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-1.3.0-final', 'sophonweb-2.2.1-final'))

        pv = meta.get_compatible_versions('transwarp-6.0.2-final')
        self.assert_vrange_equal(pv.get('tdc')[0], ('tdc-2.0.0-rc3', 'tdc-2.0.0-rc3'))
        self.assert_vrange_equal(pv.get('sophonweb')[0], ('sophonweb-2.2.0-final', 'sophonweb-2.2.1-final'))

    def test_get_tdc_version_range(self):
        meta = ProductReleaseMeta(self.tdc2ex_yml)
        pv = meta.get_tdc_version_range('sophonweb-1.3.0-final')
        self.assert_vrange_equal(pv, ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc1'))

        pv = meta.get_tdc_version_range('sophonweb-1.4.0-final')
        self.assert_vrange_equal(pv, ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc1'))

        pv = meta.get_tdc_version_range('sophonweb-2.2.0-final')
        self.assert_vrange_equal(pv, ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc3'))

        pv = meta.get_tdc_version_range('sophonweb-2.2.1-final')
        self.assert_vrange_equal(pv, ('tdc-2.0.0-rc3', 'tdc-2.0.0-rc3'))

        pv = meta.get_tdc_version_range()
        self.assert_vrange_equal(pv, ('tdc-2.0.0-rc0', 'tdc-2.0.0-rc3'))
