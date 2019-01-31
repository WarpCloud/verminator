#!/usr/bin/env python3
from ruamel.yaml import YAML
from flex_version import FlexVersion
import logging

logger = logging.getLogger(__name__)


class Instance(object):
    """An versioned instance
    """

    def __init__(self, instance_type, major_version, **kwargs):
        self.instance_type = instance_type
        self.major_version = major_version

        self.min_tdc_version = FlexVersion.parse_version(
                kwarges.get('min-tdc-version', none)
            )
        self.max_tdc_version = FlexVersion.parse_version(
            kwarges.get('max-tdc-version', none))

        if FlexVersion.compare(self.min_tdc_version, self.max_tdc_version) > 0:
            logger.error('Invalid min-max tdc version range for %s %s' %
                         (self.instance_type, self.major_version))

        self._hot_fix_ranges = list()
        self.hot_fix_ranges = kwargs.get('hot-fix-ranges', list)

        self._images = dict()
        self.images = kwargs.get('images', dict())

        self._releases = dict()
        self.releases = kwargs.get('releases', dict())

    @property
    def hot_fix_ranges(self):
        return self._hot_fix_ranges

    @hot_fix_ranges.setter
    def hot_fix_ranges(self, val):
        for item in val:
            max = FlexVersion.parse_version(item.get('max'))
            min = FlexVersion.parse_version(item.get('min'))
            if FlexVersion.compare(min, max) > 0:
                logging.error('Invalid hot fix range for %s %s' %
                              (self.instance_type, self.major_version))
            self._hot_fix_ranges.append((min, max))

    @property
    def images(self):
        return self._images.items()

    @images.setter
    def images(self, val):
        for item in val:
            name = item.get('name')
            variable = item.get('variable')
            if variable not in self._images:
                self._images[variable] = name
            else:
                logger.warning(
                    'Duplicated image variables definitions for %s %s' % (
                        self.instance_type, self.major_version
                    )
                )

    @property
    def releases(self):
        return self._releases.values()

    @releases.setter
    def releases(self, releases_data):
        for release in releases_data:
            self._add_release(releases_data)

    def add_release(self, release_data):
        r = ReleaseMeta(release_dat)
        self._release[r.release_version] = r


class ReleaseMeta(object):

    def __init__(self, instance_type, val):
        self.instance_type = instance_type
        self.release_version = FlexVersion.parse_version(
            val.get('release-version'))
        self.is_final = val.get('final', False)

        self.image_version = dict()
        for img, ver in val.get('image-version', dict()).items():
            self.image_version[img] = FlexVersion.parse_version(ver)

        self.dependencies = dict()
        for dep in val.get('dependencies', list):
            instance_type = dep.get('type')
            max_ver = dep.get('max-version')
            min_ver = dep.get('min-version')

            if FlexVersion.compare(min_ver, max_ver) > 0:
                logger.error('Invalid min - max version declaim for dependency of %s for %s %s'
                             % (instance_type,
                                self.instance_type,
                                self.release_version)
                             )

            if instance_type in self.dependencies:
                logger.error('Duplicated dependency of %s for %s %s' %
                             (instance_type, self.instance_type,
                              self.release_version))
            else:
                self.dependencies[instance_type] = (min_ver, max_ver)


if __name__ == '__main__':
    from ruamel.yaml import YAML
    yaml = YAML()
    dat = yaml.load(
        open('/home/chenxm/Documents/Workspace/product-meta/instances/hdfs/5.2/images.yaml'))
    print(dat)
