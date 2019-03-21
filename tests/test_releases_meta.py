import unittest
from pathlib import Path

from verminator.releasemeta import ProductReleaseMeta


class ProductReleaseMetaCase(unittest.TestCase):

    def setUp(self):
        this_file = Path(__file__)
        self.tdc_yml = this_file.parent.joinpath('releasesmeta/tdc2ex.yml')

    def test_get_tdc_version_range(self):
        meta = ProductReleaseMeta(self.tdc_yml)
        releases = [str(i) for i in meta.major_versioned_releases.keys()]
        # meta.get_compatible_versions('tdc-2.0.0-rc1')
        meta.get_compatible_versions('sophonweb-2.2.0-final')
