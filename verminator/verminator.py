#!/usr/bin/env python3
from pathlib import Path

from .config import VerminatorConfig as VC
from .utils import *

__all__ = ['Instance', 'VersionedInstance', 'Release']


class Instance(object):
    def __init__(self, instance_type, instance_folder):
        self.instance_folder = Path(instance_folder)
        self.instance_type = instance_type
        self.versioned_instances = dict()  # {short_version: Instance}

        for ver in self.instance_folder.iterdir():
            image_file = ver.joinpath('images.yaml')
            dat = yaml.load(open(image_file))
            ins = VersionedInstance(**dat)
            self.add_versioned_instance(ver.name, ins)

    def add_versioned_instance(self, short_version, instance):
        assert short_version not in self.versioned_instances, \
            'Duplicated version %s for instance %s' % (short_version, self.instance_type)
        self.versioned_instances[short_version] = instance

    def get_versioned_instance(self, short_version):
        return self.versioned_instances.get(short_version, None)

    def create_release(self, version):
        version = parse_version(version)
        short_version = '{}.{}'.format(version.major, version.minor)

        if short_version in self.versioned_instances:
            self.versioned_instances[short_version].create_release(version)
        else:
            latest_short_version = sorted(self.versioned_instances.keys(), reverse=True)[0]
            latest_instance = self.versioned_instances[latest_short_version]
            new_instance = copy.deepcopy(latest_instance)
            new_instance.major_version = short_version
            new_instance._hot_fix_ranges = list()
            new_instance._releases = dict()
            ref_release = latest_instance.find_latest_final_release(product_name(version))
            new_instance.create_release(version, ref_release)
            self.versioned_instances[short_version] = new_instance

            self.instance_folder.joinpath(short_version).mkdir()

    def dump(self):
        for ver, ins in self.versioned_instances.items():
            version_folder = self.instance_folder.joinpath(ver)
            if not version_folder.exists():
                version_folder.mkdir(parents=True)
            image_file = version_folder.joinpath('images.yaml')
            yaml_str = ins.to_yaml()
            if yaml_str:
                with open(image_file, 'w') as of:
                    of.write(yaml_str)


class VersionedInstance(object):
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
        if product_name(r.release_version) == VC.OEM_NAME \
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

    def create_release(self, version, from_release=None):
        """Create a new release version
        """
        version = parse_version(version)
        assert version not in self._releases, 'Duplicated new version {} for {} {}'.format(
            version, self.instance_type, self.major_version
        )
        if from_release is None:
            from_release = self.find_latest_final_release(product_name(version))
            assert from_release is not None, \
                'No valid final version found in {}, {} as reference to create {}'.format(
                    self.instance_type, self.major_version, version
                )
        new_release = from_release.create_release(version)
        self._releases[version] = new_release

    def find_latest_final_release(self, product=None):
        """Find the latest release version.
        """
        latest_release = None
        for r in self.ordered_releases[::-1]:
            if r.is_final:
                latest_release = r
                if product and product_name(r.release_version) == product:
                    break  # found the latest final version with the same prefix
                elif not product:
                    break
        return latest_release

    def validate(self, release_meta):
        if not self._is_third_party():
            # Third-party images, ignored
            self._validate_final_flag()
            self._validate_hot_fix_ranges()
            self._validate_tdc_not_dependent_on_other_product_lines()
            self._validate_releases(release_meta)

    def _is_third_party(self):
        # Third-party images without product name
        # e.g., weblogic, nexus
        sample = list(self._releases.values())[0]
        product = product_name(sample.release_version)
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
            product = product_name(release.release_version)
            if product == VC.OEM_NAME:
                for dep, (minv, maxv) in release.dependencies.items():
                    if product_name(minv) != product:
                        print('Warning: TDC should be independent product, instance "{}", {}, dep "{}"'
                              .format(release.instance_type, release.release_version, dep))

    def _validate_releases(self, releasemeta):
        for r in self.ordered_releases:

            # Get compatible version ranges for each product
            #   {product: [(minv, maxv), (minv, maxv)]}
            cv = releasemeta.get_compatible_versions(r.release_version)

            # Filter vrange by tdc min-max version
            minor_versioned_only = is_minor_versioned_only(r.release_version)
            minv = parse_version(self._min_tdc_version, minor_versioned_only)
            maxv = parse_version(self._max_tdc_version, minor_versioned_only)

            if product_name(r.release_version) == VC.OEM_NAME:
                for pname in cv:
                    filtered = list()
                    for v in cv[pname]:
                        fv = filter_vrange(v, (minv, maxv))
                        if fv is not None:
                            filtered.append(fv)
                    if not filtered:
                        print('Warning: Release {} of instance "{}" is filtered out by min-max tdc version.'
                              .format(r.release_version, r.instance_type))

                    cv[pname] = filtered

            # Validate the dependency versions
            for instance, vrange in r.dependencies.items():
                product = product_name(vrange[0])
                if product in cv:
                    if len(cv[product]) == 0:
                        raise ValueError(
                            'No valid version range declared for instance {}, version {} in releasemeta'
                                .format(self.instance_type, r.release_version)
                        )
                    minv, maxv = cv[product][0]
                else:
                    minv, maxv = vrange

                if minv != vrange[0]:
                    print('Warning: incompatible min version {} (should be {}) for dep "{}" of release "{}" version {}'
                          .format(vrange[0], minv, instance, r.instance_type, r.release_version))

                if maxv != vrange[1]:
                    print('Warning: incompatible max version {} (should be {}) for dep "{}" of release "{}" version {}'
                          .format(vrange[1], maxv, instance, r.instance_type, r.release_version))

                r.dependencies[instance] = (minv, maxv)

    def to_yaml(self):

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

    def convert_oem(self):
        self._min_tdc_version = replace_product_name(self._min_tdc_version, VC.OEM_NAME, VC.OFFICIAL_NAME)
        self._max_tdc_version = replace_product_name(self._max_tdc_version, VC.OEM_NAME, VC.OFFICIAL_NAME)
        self._hot_fix_ranges = [
            (
                replace_product_name(minv, VC.OEM_NAME, by=VC.OFFICIAL_NAME),
                replace_product_name(maxv, VC.OEM_NAME, by=VC.OFFICIAL_NAME)
            ) for minv, maxv in self._hot_fix_ranges
        ]
        for rver, release in self._releases.items():
            self._releases[rver] = release.convert_oem(VC.OEM_NAME, VC.OFFICIAL_NAME)


class Release(object):
    """ The metadata of a specific versioned release.
    """

    def __init__(self, instance_type, val):
        self.instance_type = instance_type
        self.release_version = parse_version(val.get('release-version'))
        self.is_final = val.get('final', False)

        # Images
        self.image_version = dict()  # {image_var: version}
        for img, ver in val.get('image-version', dict()).items():
            self.image_version[img] = parse_version(ver)

        # Dependencies
        self.dependencies = dict()   # {instance_type: (minv, maxv)}
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

    def convert_oem(self, oemname, by=VC.OFFICIAL_NAME):
        self.release_version = replace_product_name(self.release_version, oemname, by)
        for image_name, ver in self.image_version.items():
            self.image_version[image_name] = replace_product_name(ver, oemname, by)
        for instance, vrange in self.dependencies.items():
            minv, maxv = vrange
            self.dependencies[instance] = (
                replace_product_name(minv, oemname, by),
                replace_product_name(maxv, oemname, by)
            )
        return self

    def create_release(self, version):
        """Clone a new versioned release with reference to self.
        """
        version = parse_version(version)
        is_minor_versioned = is_minor_versioned_only(version)
        # assert get_product_name(version) == get_product_name(self.release_version), \
        #     'The reference version {} should be the same product: {}'.format(
        #         self.release_version, version
        #     )
        new_release = copy.deepcopy(self)
        new_release.release_version = version
        for img, ver in new_release.image_version.items():
            if product_name(ver) == product_name(self.release_version):
                new_release.image_version[img] = version
            elif is_minor_versioned:
                new_release.image_version[img] = to_minor_version(ver)
        for dep, (minv, maxv) in new_release.dependencies.items():
            if product_name(minv) == product_name(self.release_version):
                new_release.dependencies[dep] = (version, version)
            elif is_minor_versioned:
                new_release.dependencies[dep] = (to_minor_version(minv), to_minor_version(maxv))
        return new_release
