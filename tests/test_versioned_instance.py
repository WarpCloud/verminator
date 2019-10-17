import unittest
from pathlib import Path

from verminator.releasemeta import ProductReleaseMeta
from verminator.utils import *
from verminator.verminator import VersionedInstance


class VersionedInstanceCase(unittest.TestCase):

    def setUp(self):
        this_file = Path(__file__)
        self.tdc3ex_yml = this_file.parent.joinpath('releasesmeta/tdc3ex.yml')
        self.versioned_instance_yml = this_file.parent.joinpath('releasesmeta/versioned_instance.yml')

    def test_official(self):
        meta = ProductReleaseMeta(self.tdc3ex_yml)
        versioned_instance = VersionedInstance(**yaml.load(open(self.versioned_instance_yml)))
        self.assertTrue(str(versioned_instance.min_tdc_version) == 'tdc-2.0.0-rc0')
        self.assertTrue(str(versioned_instance.max_tdc_version) == 'tdc-2.0.0-rc9')
        versioned_instance._validate_releases(meta)
        self.assertTrue(versioned_instance is not None)
        release = versioned_instance.get_release('5.2.2')
        for dep in release.dependencies:
            self.assertTrue(str(release.dependencies[dep][0]) == 'transwarp-5.2.2-final')
            self.assertTrue(str(release.dependencies[dep][1]) == 'transwarp-5.2.2-final')
