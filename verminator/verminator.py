#!/usr/bin/env python3
# This library deals with the instances images of product-meta,
# which has following folder structure as mapped by the data objects:
# product-meta:
# |__ ...
# |__instances [class Instance]
#    |__version1 [class VersionedInstance]
#       |__images.yml [class Release]
from pathlib import Path

from .config import verminator_config as VC
from .utils import *

__all__ = ['Instance', 'VersionedInstance', 'Release']


class Instance(object):
    def __init__(self, instance_type, instance_folder, omit_sample=False):
        self.instance_type = instance_type
        self.instance_folder = Path(instance_folder)
        self.versioned_instances = dict()  # {major_version_num: VersionedInstance}

        if omit_sample and instance_type.startswith('_'):
            # Omit instance with private symbol '_'
            return

        for ver in self.instance_folder.iterdir():
            if omit_sample and ver.name.startswith('_'):
                # Omit instance version with private symbol '_'
                continue
            image_file = ver.joinpath('images.yaml')
            if not image_file.exists():
                # Omit subfolder without valid images yaml
                continue
            dat = yaml.load(open(image_file), Loader=yaml.FullLoader)
            ins = VersionedInstance(**dat)
            self.add_versioned_instance(ver.name, ins)

    def add_versioned_instance(self, major_version_num, instance):
        assert major_version_num not in self.versioned_instances, \
            'Duplicated version %s for instance %s' % (major_version_num, self.instance_type)
        self.versioned_instances[major_version_num] = instance

    def get_versioned_instance(self, major_version_num):
        return self.versioned_instances.get(major_version_num, None)

    def create_release(self, version):
        """Create a new release and add to appropriate VersionedInstance.

        The version is preferentially added to VersionedInstance containing its
        corresponding major version. Otherwise a new VersionedInstance created.
        """
        version = parse_version(version)
        major_version_num = '{}.{}'.format(version.major, version.minor)

        # Find VersionedInstance which contains the major version
        ref_instance = None
        if major_version_num in self.versioned_instances:
            ref_instance = self.versioned_instances[major_version_num]
        else:
            major_version = to_major_version(version)  # with prefix say tdc-2.0
            for versioned_ins in self.versioned_instances.values():
                if versioned_ins.has_release(major_version):
                    ref_instance = versioned_ins
                    break

        if ref_instance is not None:
            ref_instance.create_release(version, None, True)
        else:
            # Find the latest release with the same product as reference
            ref_release = None
            for ver_num in sorted(self.versioned_instances.keys(), reverse=True):
                ins = self.versioned_instances[ver_num]
                latest_r = ins.find_latest_release(product_name(version))
                if latest_r is not None:
                    ref_release = latest_r
                    ref_instance = ins
                if ref_instance is not None:
                    break

            if ref_instance is None:
                raise ValueError('No valid final reference release found for creating {} of {}'.format(
                    version, ref_instance.instance_type
                ))

            new_instance = copy.deepcopy(ref_instance)
            new_instance.major_version = major_version_num
            new_instance._hot_fix_ranges = list()
            new_instance._releases = dict()
            new_instance.create_release(version, ref_release, with_major=True)
            self.versioned_instances[major_version_num] = new_instance

    def has_release(self, release_version):
        for ver, versioned_ins in self.versioned_instances.items():
            if versioned_ins.has_release(release_version):
                return True
        return False

    def validate(self, release_meta, sync_releases=False):
        """Validate all versioned instances and releases"""
        self._validate_declared_tdc_releases(release_meta)
        # Validate specific versioned instance
        for ver, versioned_ins in self.versioned_instances.items():
            print(self.instance_folder.joinpath(ver))
            versioned_ins.validate(release_meta, sync_releases)

    def _validate_declared_tdc_releases(self, release_meta):
        """WARP-38519: The declared TDC releases in release_meta.yaml
        should be also declared in images.yaml
        """
        tdc_releases = [i for i in release_meta.get_releases().keys() if i.prefix == VC.OEM_NAME]

        # Check if the instance contains TDC versioned releases
        found = False
        for ver, versioned_ins in self.versioned_instances.items():
            for release in versioned_ins.releases:
                if release.release_version.prefix == VC.OEM_NAME:
                    found = True
                    break

        if found:
            for tdc_version in tdc_releases:
                if not self.has_release(tdc_version):
                    raise ValueError("Absent TDC release '{}' defined in meta for instance {}".format(
                        tdc_version, self.instance_type
                    ))

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

        # The major version corresponds to chart version in helm.
        self.major_version = parse_version(kwargs.get('major-version'))

        self._min_tdc_version = parse_version(
            kwargs.get('min-tdc-version', None)
        )

        self._max_tdc_version = parse_version(
            kwargs.get('max-tdc-version', None))

        if self._min_tdc_version.compares(self._max_tdc_version) > 0:
            raise ValueError('Invalid min-max tdc version range for %s %s' %
                             (self.instance_type, self.major_version))

        self._hot_fix_ranges = list()  # [(minv, maxv)]
        for item in kwargs.get('hot-fix-ranges', list):
            self.add_hot_fix_range(item.get('min'), item.get('max'))

        self._images = dict()  # {var: { name:name, role: role, roles: []}}
        for item in kwargs.get('images', dict()):
            self.add_image(item)

        self._releases = dict()  # {release_ver: Release}
        for release in kwargs.get('releases', dict()):
            self.add_release(release)

    @property
    def min_tdc_version(self):
        """Get the """
        assert not is_major_version(self._min_tdc_version), \
            'The min tdc version should be a valid final version'
        return self._min_tdc_version

    @property
    def max_tdc_version(self):
        assert not is_major_version(self._max_tdc_version), \
            'The max tdc version should be a valid final version'
        return self._max_tdc_version

    @property
    def hot_fix_ranges(self):
        """Get a list of hot-fix ranges in form [(minv, maxv)]
        """
        return self._hot_fix_ranges

    @property
    def images(self):
        """Get a dict of image variables and names
        """
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
            lambda x, y: x.release_version.compares(y.release_version)
        ))

    def add_hot_fix_range(self, _min, _max):
        """Add a new hot-fix range to VersionedInstance from raw data.
        """
        if isinstance(_min, str):
            _min = parse_version(_min)
        if isinstance(_max, str):
            _max = parse_version(_max)

        if _min.compares(_max) > 0:
            raise ValueError(
                'Invalid hot fix range for %s %s' %
                (self.instance_type, self.major_version)
            )

        self._hot_fix_ranges.append((_min, _max))

    def add_image(self, image_dat):
        """Add a new image to VersionedInstance from raw data.
        """
        name = image_dat.get('name')
        variable = image_dat.get('variable')
        role = image_dat.get('role', None)
        roles = image_dat.get('roles', None)
        if variable not in self._images:
            self._images[variable] = {
                'name': name,
                'variable': variable,
                'role': role,
                'roles': roles
            }
        else:
            raise ValueError(
                'Duplicated image variables definitions for %s %s' % (
                    self.instance_type, self.major_version
                ))

    def add_release(self, release_dat):
        """Add a new release to VersionedInstance from raw data.
        """
        r = Release(self.instance_type, release_dat)
        # Validate the image completeness
        for image_name in r.image_version:
            assert image_name in self._images, \
                'Image name %s of release %s %s should be declared first' % (
                    image_name, self.instance_type, self.major_version)
        self._releases[r.release_version] = r

    def remove_release(self, release_version):
        return self._releases.pop(release_version)

    def get_release(self, release_version, default=None):
        """Get a release defined in the VersionedInstance
        """
        release_version = parse_version(release_version)
        return self._releases.get(release_version, default)

    def has_release(self, release_version):
        """Check if a specific version is defined in the VersionedInstance
        """
        release_version = parse_version(release_version)
        return release_version in self._releases

    def create_release(self, version, from_release=None, with_major=False):
        """Create a new release with version from @from_release or
        """
        version = parse_version(version)
        if version in self._releases:
            print('Warning: Duplicated new version {} for {} {}, skip'.format(
                version, self.instance_type, self.major_version
            ))
            return

        if from_release is None:
            from_release = self.find_latest_release(product_name(version))
            assert from_release is not None, \
                'No valid final version found in {}, {} as reference to create {}'.format(
                    self.instance_type, self.major_version, version
                )

        new_release = from_release.clone_as(version)
        self._releases[version] = new_release

        if with_major:
            major_version = to_major_version(version)
            if major_version not in self._releases:
                minor_release = new_release.clone_as(major_version)
                minor_release.is_final = False
                self._releases[major_version] = minor_release
            else:
                print('Duplicated major version {} for {}, {}, skip'.format(
                    major_version, self.instance_type, self.major_version))

    def convert_oem(self):
        self._min_tdc_version = replace_product_name(self._min_tdc_version, VC.OEM_NAME, VC._OEM_ORIGIN)
        self._max_tdc_version = replace_product_name(self._max_tdc_version, VC.OEM_NAME, VC._OEM_ORIGIN)
        self._hot_fix_ranges = [
            (
                replace_product_name(minv, VC.OEM_NAME, by=VC._OEM_ORIGIN),
                replace_product_name(maxv, VC.OEM_NAME, by=VC._OEM_ORIGIN)
            ) for minv, maxv in self._hot_fix_ranges
        ]
        for rver, release in self._releases.items():
            self._releases[rver] = release.convert_oem(VC.OEM_NAME, VC._OEM_ORIGIN)

    def find_latest_release(self, product=None, is_final=False):
        """Find the latest release by product name .
        """
        latest_release = None
        for r in self.ordered_releases[::-1]:
            # Ignore non-final releases
            if is_final and not r.is_final:
                continue

            # Find the first release (reversely) for given product
            rp = product_name(r.release_version)
            if product is not None:
                latest_release = r if rp == product else None
            else:
                latest_release = r if rp != product else None

            if latest_release is not None:
                break

        return latest_release

    def validate(self, release_meta, sync_releases=True):
        """Validate properties and fix errors if possible for versioned instance"""
        # Remove deprecated versions, WARP-38528
        if sync_releases:
            self._remove_deprecated_releases(release_meta)

        # Update tdc min-max versions
        self._update_tdc_minmax_version(release_meta)

        # Validate each release
        for ver, release in self._releases.items():
            release.validate_final_flag()
            release.validate_tdc_minmax_version(self._min_tdc_version, self._max_tdc_version)

        self._validate_hot_fix_ranges()
        # self._validate_tdc_not_dependent_on_other_product_lines()  # Disable it for now
        self._validate_releases(release_meta)
        self._validate_argodb_images(release_meta)

    def _remove_deprecated_releases(self, release_meta):
        """WARP-38528: Sync instance releases with meta info while removing undeclared old releases"""
        for release in self.ordered_releases:
            compilable_versions = release_meta.get_compatible_versions(release.release_version, self_appended=False)
            product = release.release_version.prefix
            found = False
            for vrange in compilable_versions.get(product, list()):
                if release.release_version.in_range(vrange[0], vrange[1]):
                    found = True
                    break
            if product is not None and not found:
                print('Warning: remove undeclared release {} of instance {}, {} (WARP-38528)'.format(
                    release.release_version, self.instance_type, self.major_version
                ))
                self.remove_release(release.release_version)

    def _update_tdc_minmax_version(self, release_meta):
        global_range = release_meta.get_tdc_version_range()
        tdc_vranges = list()
        for release in self.ordered_releases:
            # The third party release (without version prefix) takes the global version range
            if release.is_third_party() and global_range is not None:
                tdc_vranges.append(global_range)
                continue

            # Otherwise get the precise compatible product version range
            vrange = release_meta.get_tdc_version_range(release.release_version)
            if vrange is not None:
                tdc_vranges.append(vrange)
            else:
                print('Warning: not found a valid tdc version range for {}, {}. Use the global range instead'
                      .format(release.instance_type, release.release_version))
                if global_range is not None:
                    tdc_vranges.append(global_range)

        if len(tdc_vranges) > 0:
            self._min_tdc_version = sorted([i[0] for i in tdc_vranges], key=cmp_to_key(
                lambda x, y: x.compares(y)
            ))[0]
            self._max_tdc_version = sorted([i[1] for i in tdc_vranges], key=cmp_to_key(
                lambda x, y: x.compares(y)
            ))[-1]
        else:
            raise ValueError('At least a valid release is required for {}, {}'.format(
                self.instance_type, self.major_version)
            )

    def _validate_hot_fix_ranges(self):
        """Validae hot-fix ranges for versioned instance"""

        def is_version_in_hot_fix_range(version):
            found = False
            for _min, _max in self._hot_fix_ranges:
                if version.in_range(_min, _max):
                    found = True
                    break
            assert found is True, \
                'Release version %s of "%s" should be located in a specific hot-fix range' % \
                (version, self.instance_type)

        for release in self._releases.values():
            v = release.release_version
            try:
                is_version_in_hot_fix_range(v)
            except AssertionError as e:
                print('Warning {}'.format(str(e)))
                self.add_hot_fix_range(v, v)

        # Merge continuous hot-fix ranges
        # Differentiate complete and minor-versioned-only versions
        complete_ranges = list()
        major_versions = list()
        for minv, maxv in self._hot_fix_ranges:
            im_minv = is_major_version(minv)
            im_maxv = is_major_version(maxv)
            assert im_minv == im_maxv, 'Min and max should take the same form'
            if im_minv:
                major_versions.append((minv, maxv))
            else:
                complete_ranges.append((minv, maxv))
        self._hot_fix_ranges = concatenate_vranges(complete_ranges) + \
                               concatenate_vranges(major_versions)

    def _validate_tdc_not_dependent_on_other_product_lines(self):
        for release in self._releases.values():
            product = product_name(release.release_version)
            if product == VC.OEM_NAME:
                for dep, (minv, maxv) in release.dependencies.items():
                    if product_name(minv) != product:
                        print('Warning: TDC should better be independent: {}, {} depends on {}'
                              .format(release.instance_type, release.release_version, dep))

    def _validate_releases(self, release_meta):
        """Validate all releases of the instance."""
        ## For debugging
        # if self.instance_type == 'sophon' and str(self.major_version) == '2.3':
        #     print(self.instance_type, self.major_version)

        for r in self.ordered_releases:
            # Get compatible version ranges for each product
            #   {product: [(minv, maxv), (minv, maxv)]}
            # WARP-34008: support instance-specific constraints
            cv = release_meta.get_compatible_versions(r.release_version, instance_name=r.instance_type)

            # Filter vrange by tdc min-max version
            _is_major_version = is_major_version(r.release_version)
            minv = parse_version(self._min_tdc_version, _is_major_version)
            maxv = parse_version(self._max_tdc_version, _is_major_version)
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
                if product not in cv:
                    minv, maxv = vrange
                else:
                    if len(cv[product]) == 0:
                        raise ValueError(
                            'No valid version range declared for instance {}, version {} in releasemeta'
                                .format(self.instance_type, r.release_version))
                    else:
                        # TODO: it seems safe to merge dependency release versions
                        minv, maxv = concatenate_vranges(cv[product], hard_merging=True)[0]
                if minv != vrange[0]:
                    print('Warning: incompatible min version {} (should be {}) for dep "{}" of release "{}" version {}'
                          .format(vrange[0], minv, instance, r.instance_type, r.release_version))
                if maxv != vrange[1]:
                    print('Warning: incompatible max version {} (should be {}) for dep "{}" of release "{}" version {}'
                          .format(vrange[1], maxv, instance, r.instance_type, r.release_version))
                r.dependencies[instance] = (minv, maxv)

    def _validate_argodb_images(self, release_meta):
        """
        Fix custom terminal image version for argodb, WARP-38405
        """
        if self.instance_type == 'terminal':
            for release_ver, release in self._releases.items():
                if release_ver.prefix != 'argodb':
                    continue
                tdc_vrange = release_meta.get_tdc_version_range(release_ver, self.instance_type)
                terminal_image_ver = tdc_vrange[1] if tdc_vrange is not None else None
                release.image_version['terminal_image'] = terminal_image_ver
                print('WARNING: set terminal image for argodb {} as {} (WARP-38405)'
                      .format(release_ver, terminal_image_ver))

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
        for var, data in self.images:
            image_dat = {key: value for key, value in data.items() if value is not None}
            res['images'].append(image_dat)

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
        self.release_version = parse_version(val.get('release-version'))
        self.is_final = val.get('final', False)

        # Images
        self.image_version = dict()  # {image_var: version}
        for img, ver in val.get('image-version', dict()).items():
            self.image_version[img] = parse_version(ver)

        # Dependencies
        self.dependencies = dict()  # {instance_type: (minv, maxv)}
        for dep in val.get('dependencies', list):
            instance_type = dep.get('type')
            _max_ver = parse_version(dep.get('max-version'))
            _min_ver = parse_version(dep.get('min-version'))

            if _min_ver.compares(_max_ver) > 0:
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

    def convert_oem(self, oemname, by=VC._OEM_ORIGIN):
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

    def clone_as(self, version):
        """Clone a new versioned release with reference to self.
        """
        version = parse_version(version)
        _is_major_version = is_major_version(version)
        new_release = copy.deepcopy(self)
        new_release.release_version = version
        new_release.is_final = not _is_major_version
        for img, ver in new_release.image_version.items():
            if product_name(ver) == product_name(self.release_version):
                new_release.image_version[img] = version
            elif _is_major_version:
                new_release.image_version[img] = to_major_version(ver)
        for dep, (minv, maxv) in new_release.dependencies.items():
            if product_name(minv) == product_name(self.release_version):
                new_release.dependencies[dep] = (version, version)
            elif _is_major_version:
                new_release.dependencies[dep] = (to_major_version(minv), to_major_version(maxv))
        return new_release

    def validate_tdc_minmax_version(self, minv, maxv):
        """Validate the release version should fall into min-max tdc range.
        """
        if product_name(self.release_version) == VC.OEM_NAME \
                and self.release_version.suffix is not None:
            assert self.release_version.in_range(minv, maxv), \
                'The release {} of "{}" should in min-max tdc versions ({}, {})'.format(
                    self.release_version, self.instance_type,
                    minv, maxv
                )

    def is_major_version(self):
        return is_major_version(self.release_version)

    def is_third_party(self):
        # Third-party images without product name
        # e.g., weblogic, nexus
        product = product_name(self.release_version)
        if product is None and self.release_version.suffix is None:
            return True
        return False

    def validate_final_flag(self):
        """Validate is_final flag and version format
        """
        is_valid_final = False
        if self.release_version.suffix is not None or self.is_third_party():
            is_valid_final = True
        if self.is_final and not is_valid_final:
            raise ValueError('The final version {} of instance {} is illegal'.format(
                self.release_version, self.instance_type
            ))
