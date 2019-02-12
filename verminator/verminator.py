#!/usr/bin/env python3

from .utils import *

__all__ = ['Instance']

# Customized version suffix ordering
FlexVersion.ordered_suffix = ['rc', 'final', None]


class Instance(object):
    """A versioned instance
    """

    def __init__(self, **kwargs):
        self.instance_type = kwargs.get('instance-type')
        self.major_version = kwargs.get('major-version')

        self._min_tdc_version = FlexVersion.parse_version(
            kwargs.get('min-tdc-version', None)
        )
        self._max_tdc_version = FlexVersion.parse_version(
            kwargs.get('max-tdc-version', None))

        if FlexVersion.compares(self._min_tdc_version, self._max_tdc_version) > 0:
            raise ValueError('Invalid min-max tdc version range for %s %s' %
                             (self.instance_type, self.major_version))

        self._hot_fix_ranges = list()
        for item in kwargs.get('hot-fix-ranges', list):
            self.add_host_fix_range(item.get('min'), item.get('max'))

        self._images = dict()
        for item in kwargs.get('images', dict()):
            self.add_image(item)

        self._releases = dict()
        for release in kwargs.get('releases', dict()):
            self.add_release(release)

    @property
    def min_tdc_version(self):
        return self._min_tdc_version

    @property
    def max_tdc_version(self):
        return self._max_tdc_version

    @property
    def hot_fix_ranges(self):
        return self._hot_fix_ranges

    def add_host_fix_range(self, _min, _max):
        if isinstance(_min, str):
            _min = FlexVersion.parse_version(_min)
        if isinstance(_max, str):
            _max = FlexVersion.parse_version(_max)

        if FlexVersion.compares(_min, _max) > 0:
            raise ValueError(
                'Invalid hot fix range for %s %s' %
                (self.instance_type, self.major_version)
            )

        # TODO: Should we merge overlapping fix ranges?
        self._hot_fix_ranges.append((_min, _max))

    @property
    def images(self):
        return self._images.items()

    def add_image(self, image_dat):
        name = image_dat.get('name')
        variable = image_dat.get('variable')
        if variable not in self._images:
            self._images[variable] = name
        else:
            raise ValueError(
                'Duplicated image variables definitions for %s %s' % (
                    self.instance_type, self.major_version
                ))

    @property
    def releases(self):
        """Get a list of releases
        """
        return self._releases.values()

    def add_release(self, release_dat):
        r = Release(self.instance_type, release_dat)

        # Validate the image completeness
        for image_name in r.image_version:
            assert image_name in self._images, \
                'Image name %s of release %s should be declared first' % (
                    image_name, self.instance_type)

        # Validate release that should fall into a specific hot fix range
        found = False
        for _min, _max in self._hot_fix_ranges:
            if FlexVersion.in_range(r.release_version, _min, _max):
                found = True
                break
        assert found is True, \
            'Release version %s should be located in a specific hot-fix range' % (
                r.release_version)

        self._releases[r.release_version] = r

    def get_release(self, release_version, default=None):
        release_version = parse_version(release_version)
        return self._releases.get(release_version, default)

    def ordered_releases(self, reverse=False):
        """ Get a list of ordered releases by versions.
        """
        return sorted(self._releases.values(), key=cmp_to_key(
            lambda x, y: FlexVersion.compares(
                x.release_version, y.release_version)
        ), reverse=reverse)

    def validate_releases(self, release_meta):
        for r in self.ordered_releases():
            if r.is_final and not is_valid_final(r.release_version):
                raise ValueError('The final version %s is illage' % r.release_version)

            cv = get_compatible_versions(
                release_meta,
                r.release_version
            )

            # Filter vrange by tdc min-max version
            for pname in cv:
                other = (self.min_tdc_version, self.max_tdc_version)
                filtered = list()
                for vrange in cv[pname]:
                    fv = filter_vrange(vrange, other)
                    if fv is not None:
                        filtered.append(fv)
                cv[pname] = filtered

            print(r.release_version, cv)


class Release(object):
    """ The metadata of a specific versioned release.
    """

    def __init__(self, instance_type, val):
        self.instance_type = instance_type
        self.release_version = FlexVersion.parse_version(
            val.get('release-version'))
        self.is_final = val.get('final', False)

        # Images
        self.image_version = dict()
        for img, ver in val.get('image-version', dict()).items():
            self.image_version[img] = FlexVersion.parse_version(ver)

        # Dependencies
        self.dependencies = dict()
        for dep in val.get('dependencies', list):
            instance_type = dep.get('type')
            _max_ver = FlexVersion.parse_version(dep.get('max-version'))
            _min_ver = FlexVersion.parse_version(dep.get('min-version'))

            if FlexVersion.compares(_min_ver, _max_ver) > 0:
                raise ValueError('Invalid min-max version declaim for dependency of %s for %s %s'
                                 % (instance_type,
                                    self.instance_type,
                                    self.release_version)
                                 )

            if instance_type in self.dependencies:
                raise ValueError('Duplicated dependency of %s for %s %s' %
                                 (instance_type, self.instance_type,
                                  self.release_version))
            else:
                self.dependencies[instance_type] = (_min_ver, _max_ver)

    def get_anchor_version(self):
        """Get the anchor release version, e.g.,
        the anchor version of transwarp-5.2.0-final is transwarp-5.2
        """
        return FlexVersion.parse_version(
            '%s-%d.%d' % (self.release_version.prefix, self.release_version.major, self.release_version.minor)
        )
