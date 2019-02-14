#!/usr/bin/env python3
import sys
from collections import OrderedDict

from .utils import *

__all__ = ['Instance', 'Release']


class Instance(object):
    """A versioned instance
    """

    def __init__(self, **kwargs):
        self.instance_type = kwargs.get('instance-type')
        self.major_version = parse_version(kwargs.get('major-version'))

        self._min_tdc_version = parse_version(
            kwargs.get('min-tdc-version', None)
        )
        self._max_tdc_version = parse_version(
            kwargs.get('max-tdc-version', None))

        if FlexVersion.compares(self._min_tdc_version, self._max_tdc_version) > 0:
            raise ValueError('Invalid min-max tdc version range for %s %s' %
                             (self.instance_type, self.major_version))

        self._hot_fix_ranges = list()  # [(minv, maxv)]
        for item in kwargs.get('hot-fix-ranges', list):
            self.add_host_fix_range(item.get('min'), item.get('max'))

        self._images = dict()  # {var: name}
        for item in kwargs.get('images', dict()):
            self.add_image(item)

        self._releases = dict()  # {release_ver: Release}
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

    @property
    def images(self):
        return self._images.items()

    @property
    def releases(self):
        """Get a list of releases
        """
        return self._releases.values()

    @property
    def ordered_releases(self):
        """ Get a list of ordered releases by versions.
        """
        return sorted(self._releases.values(), key=cmp_to_key(
            lambda x, y: FlexVersion.compares(
                x.release_version, y.release_version)
        ))

    def add_host_fix_range(self, _min, _max):
        if isinstance(_min, str):
            _min = parse_version(_min)
        if isinstance(_max, str):
            _max = parse_version(_max)

        if FlexVersion.compares(_min, _max) > 0:
            raise ValueError(
                'Invalid hot fix range for %s %s' %
                (self.instance_type, self.major_version)
            )

        self._hot_fix_ranges.append((_min, _max))

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

    def add_release(self, release_dat):
        r = Release(self.instance_type, release_dat)

        # Validate the image completeness
        for image_name in r.image_version:
            assert image_name in self._images, \
                'Image name %s of release %s should be declared first' % (
                    image_name, self.instance_type)

        # Validate the release version should fall into min-max tdc range
        if get_product_name(r.release_version) == 'tdc' \
                and r.release_version.suffix is not None:
            assert r.release_version.in_range(
                self._min_tdc_version, self._max_tdc_version
            ), 'The release {} of "{}" should in min-max tdc versions'.format(
                r.release_version, r.instance_type
            )

        # Validate release that should fall into a specific hot fix range
        self._validate_version_in_hot_fix_range(r.release_version)

        self._releases[r.release_version] = r

    def get_release(self, release_version, default=None):
        release_version = parse_version(release_version)
        return self._releases.get(release_version, default)

    def create_release(self, version):
        """Create a new release version
        """
        pass

    def validate(self, release_meta):
        if not self._is_third_party():
            # Third-party images, ignored
            self._validate_final_flag()
            self._validate_hot_fix_ranges()
            # self._validate_tdc_not_dependent_on_other_product_lines()
            self._validate_releases(release_meta)

    def _is_third_party(self):
        # Third-party images without product name
        # e.g., weblogic, nexus
        sample = list(self._releases.values())[0]
        product = get_product_name(sample.release_version)
        if product is None:
            return True
        return False

    def _validate_final_flag(self):
        for r in self._releases.values():
            # Validate is_final flag and version format
            version = parse_version(r.release_version)
            is_valid_final = True if version.suffix is not None else False
            if r.is_final and not is_valid_final:
                raise ValueError('The final version %s is illage' % r.release_version)

    def _validate_hot_fix_ranges(self):
        # Differentiate complete and minor-versioned-only versions
        complete_ranges = list()
        minor_versioned = list()
        for minv, maxv in self._hot_fix_ranges:
            im_minv = is_minor_versioned_only(minv)
            im_maxv = is_minor_versioned_only(maxv)
            assert im_minv == im_maxv, 'Min and max should take the same form'
            if im_minv:
                minor_versioned.append((minv, maxv))
            else:
                complete_ranges.append((minv, maxv))
        self._hot_fix_ranges = \
            concatenate_vranges(complete_ranges) + concatenate_vranges(minor_versioned)

    def _validate_version_in_hot_fix_range(self, version):
        found = False
        for _min, _max in self._hot_fix_ranges:
            if FlexVersion.in_range(version, _min, _max):
                found = True
                break
        assert found is True, \
            'Release version %s of "%s" should be located in a specific hot-fix range' % \
            (version, self.instance_type)

    def _validate_tdc_not_dependent_on_other_product_lines(self):
        for release in self._releases.values():
            product = get_product_name(release.release_version)
            if product == 'tdc':
                for dep, (minv, maxv) in release.dependencies.items():
                    if get_product_name(minv) != product:
                        print(('Warning: TDC should be independent of ' +
                               'other product lines instance "{}", ' +
                               'version {}, dependency "{}"')
                              .format(release.instance_type, release.release_version, dep))

    def _validate_releases(self, releasemeta):
        for r in self.ordered_releases:
            # Get compatible version ranges for each product
            cv = releasemeta.get_compatible_versions(r.release_version)

            # Filter vrange by tdc min-max version
            minor_versioned_only = is_minor_versioned_only(r.release_version)
            minv = parse_version(self.min_tdc_version, minor_versioned_only)
            maxv = parse_version(self.max_tdc_version, minor_versioned_only)
            if get_product_name(r.release_version) == 'tdc':
                for pname in cv:
                    filtered = list()
                    for vrange in cv[pname]:
                        fv = filter_vrange(vrange, (minv, maxv))
                        if fv is not None:
                            filtered.append(fv)

                    if not filtered:
                        print(('Warning: Release {} of instance "{}" ' +
                               'is filtered out by min-max tdc version.')
                              .format(r.release_version, r.instance_type))

                    cv[pname] = filtered

            # Validate the dependency versions
            for instance, vrange in r.dependencies.items():
                product = get_product_name(vrange[0])
                if product in cv:
                    if len(cv[product]) == 0:
                        raise ValueError(('No valid version range declared for ' +
                                          'instance {}, version {} in releasemeta')
                                         .format(self.instance_type, r.release_version))
                    minv, maxv = cv[product][0]
                else:
                    minv, maxv = vrange

                if minv != vrange[0]:
                    print(('Warning: incompatible min version {} ' +
                           '(should be {}) for dependency "{}" ' +
                           'of release "{}" version {}')
                          .format(vrange[0], minv, instance, r.instance_type, r.release_version))

                if maxv != vrange[1]:
                    print(('Warning: incompatible max version {} ' +
                           '(should be {}) for dependency "{}" ' +
                           'of release "{}" version {}')
                          .format(vrange[1], maxv, instance, r.instance_type, r.release_version))

                r.dependencies[instance] = (minv, maxv)

    def to_yaml(self, stream=None, **kwargs):
        # Ordered keys
        res = OrderedDict()
        res['instance-type'] = self.instance_type
        res['major-version'] = str(self.major_version)
        res['min-tdc-version'] = str(self.min_tdc_version)
        res['max-tdc-version'] = str(self.max_tdc_version)
        res['hot-fix-ranges'] = list()
        for vrange in self.hot_fix_ranges:
            res['hot-fix-ranges'].append({
                'max': str(vrange[1]),
                'min': str(vrange[0])
            })

        res['images'] = list()
        for var, name in self.images:
            res['images'].append({'variable': var, 'name': name})

        res['releases'] = list()
        for r in self.ordered_releases:
            robj = OrderedDict()
            robj['release-version'] = str(r.release_version)

            robj['image-version'] = dict()
            for img_name, ver in r.image_version.items():
                robj['image-version'][img_name] = str(ver)
            robj['dependencies'] = list()
            for instance, (minv, maxv) in r.dependencies.items():
                robj['dependencies'].append({
                    'max-version': str(maxv),
                    'min-version': str(minv),
                    'type': instance
                })
            robj['final'] = r.is_final
            res['releases'].append(robj)

        return ordered_yaml_dump(res, default_flow_style=False)


class Release(object):
    """ The metadata of a specific versioned release.
    """

    def __init__(self, instance_type, val):
        self.instance_type = instance_type
        self.release_version = parse_version(
            val.get('release-version'))
        self.is_final = val.get('final', False)

        # Images
        self.image_version = dict()
        for img, ver in val.get('image-version', dict()).items():
            self.image_version[img] = parse_version(ver)

        # Dependencies
        self.dependencies = dict()  # {instance_type: (minv, maxv)}
        for dep in val.get('dependencies', list):
            instance_type = dep.get('type')
            _max_ver = parse_version(dep.get('max-version'))
            _min_ver = parse_version(dep.get('min-version'))

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
