import unittest
import os
from pathlib import Path
from verminator.releasemeta import ProductReleaseMeta


class ProductReleaseMetaCase(unittest.TestCase):

    def setUp(self):
        this_file = Path(__file__)
        self.oem_yml = this_file.parent.joinpath('releasesmeta/oem.yml')
        self.tdc_yml = this_file.parent.joinpath('releasesmeta/tdc.yml')

    def test_official(self):
        meta = ProductReleaseMeta(self.tdc_yml)
        releases = [str(i) for i in meta.minor_versioned_releases.keys()]
        self.assertTrue('tdc-1.0' in releases)
        self.assertTrue('tdc-1.1' in releases)
        self.assertTrue('tdc-1.2' in releases)
        self.assertFalse('tdc-1.1.0-final' in releases)

    def test_oem(self):
        meta = ProductReleaseMeta(self.oem_yml)
        releases = [str(i) for i in meta.minor_versioned_releases.keys()]
        self.assertTrue('gzes-1.0' in releases)
        self.assertTrue('gzes-1.1' in releases)
        self.assertTrue('gzes-1.2' in releases)
        self.assertFalse('gzes-1.1.0-final' in releases)
