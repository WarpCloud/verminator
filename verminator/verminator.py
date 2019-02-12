#!/usr/bin/env python3
from ruamel.yaml import YAML
from flex_version import FlexVersion, VersionMeta, VersionDelta
import logging
from functools import cmp_to_key

logger = logging.getLogger(__name__)

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
            logger.error('Invalid min-max tdc version range for %s %s' %
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
    def hot_fix_ranges(self):
        return self._hot_fix_ranges

    def add_host_fix_range(self, _min, _max):
        if isinstance(_min, str):
            _min = FlexVersion.parse_version(_min)
        if isinstance(_max, str):
            _max = FlexVersion.parse_version(_max)

        if FlexVersion.compares(_min, _max) > 0:
            logging.error(
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
            logger.warning(
                'Duplicated image variables definitions for %s %s' % (
                    self.instance_type, self.major_version
                )
            )

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
        if not isinstance(release_version, VersionMeta):
            release_version = FlexVersion.parse_version(release_version)
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
            if not r.is_final:
                pass
            
            cv = release_meta.compatible_versions(r.release_version)
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
                logger.error('Invalid min-max version declaim for dependency of %s for %s %s'
                             % (instance_type,
                                self.instance_type,
                                self.release_version)
                             )

            if instance_type in self.dependencies:
                logger.error('Duplicated dependency of %s for %s %s' %
                             (instance_type, self.instance_type,
                              self.release_version))
            else:
                self.dependencies[instance_type] = (_min_ver, _max_ver)

    def get_anchor_release_version(self):
        """Get the anchor release version, e.g.,
        the anchor version of transwarp-5.2.0-final is transwarp-5.2
        """
        return FlexVersion.parse_version(
            '%s-%d.%d' % (self.prefix, self.major, self.minor)
        )


def concatenate_version_ranges(vranges):
    """ Connect and merge version ranges.
    """
    sorted_vranges = sorted(vranges, key=cmp_to_key(
        lambda x, y: FlexVersion.compares(x[0], y[0])
    ))

    res = [sorted_vranges[0]]
    for vrange in sorted_vranges[1:]:
        pmin, pmax = res[-1]
        cmin, cmax = vrange

        # Ranges connected directly:
        # * Overlapping ranges
        # * adjacent suffix versions
        if FlexVersion.in_range(cmin, pmin, pmax) \
                or cmin == pmax.add(VersionDelta(sver=1)):
            res[-1] = (pmin, cmax)
            continue

        # Ranges between rc and final
        share_non_suffix = \
            pmax.substitute(cmin, ignore_suffix=True) == VersionDelta.zero
        if share_non_suffix and pmax.suffix == 'rc' and cmin.suffix == 'final':
            res[-1] = (pmin, cmax)
            continue

        res.append(vrange)

    return res


class ProductReleaseMeta(object):
    """ Processing `releases_meta.yaml`.
    """

    def __init__(self, yaml_file):
        self.releases = dict()  # {release_name: product: (minv, maxv)}
        yaml = YAML()
        meta = yaml.load(open(yaml_file))
        self._load_releases(meta)

    def _load_releases(self, meta):
        """ Read releases meta info of product lines
        """
        for r in meta.get('Releases', list()):
            rname = FlexVersion.parse_version(r.get('release_name'))
            assert rname not in self.releases, \
                'Duplicated release meta %s' % rname

            self.releases[rname] = dict()

            products = r.get('products', list())
            for p in products:
                pname = p.get('product')
                minv = FlexVersion.parse_version(p.get('min'))
                maxv = FlexVersion.parse_version(p.get('max'))
                assert pname not in self.releases[rname], \
                    'Duplicated product %s in release %s' % (pname, rname)
                self.releases[rname][pname] = (minv, maxv)

    def product_name(self, version):
        """Get the product name given a specific version
        """
        res = set()
        if not isinstance(version, VersionMeta):
            version = FlexVersion.parse_version(version)

        for rname, products in self.releases.items():
            for pname, vrange in products.items():
                if version.in_range(vrange[0], vrange[1]):
                    res.add(pname)

        if len(res) > 1:
            raise ValueError('Conflict product names [%s] for %s' % (','.join(res), version))
        elif len(res) == 0:
            return None
        else:
            return list(res)[0]

    def compatible_versions(self, version, product=None):
        """ Given a product line name and a specific version,
        return the compatible product version ranges.
        """
        res = dict()  # {product: [(minv, maxv), (minv, maxv)]}

        if product is None:
            product = self.product_name(version)

        if product == 'tdc':
            sv = str(version)
            if sv not in self.releases:
                raise ValueError('Version %s not found' % sv)

            products = self.releases[sv]
            for pname, vrange in products.items():
                res[pname] = [vrange]
        else:
            res['tdc'] = list()
            filetered_products = list()
            for rname, products in self.releases.items():
                if product not in products:
                    # Ignore release without target product
                    continue
                minv, maxv = products.get(product)
                if not FlexVersion.in_range(version, minv, maxv):
                    # Ignore release not containing target version
                    continue
                # Remember TDC versions
                res['tdc'] = concatenate_version_ranges(
                    res['tdc'] + [(rname, rname)])
                # Extract other product versions
                for pname, vrange in products.items():
                    if pname == product:
                        continue
                    if pname not in res:
                        res[pname] = list()
                    res[pname] = concatenate_version_ranges(
                        res[pname] + [vrange])
        return res


if __name__ == '__main__':
    yaml = YAML()
    dat = yaml.load(
        open('/home/chenxm/Documents/Workspace/product-meta/instances/inceptor/5.2/images.yaml')
    )
    ins = Instance(**dat)

    meta = ProductReleaseMeta(
        '/home/chenxm/Documents/Workspace/product-meta/instances/releases_meta.yaml')
    cv = meta.compatible_versions('sophon', 'sophonweb-2.0.0-final')
    
    ins.validate_releases(meta)
