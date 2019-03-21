# Meta data for release info in yaml, e.g.,
# **********************
# Releases:
# - products:
#   - {max: tos-1.8.0.1, min: tos-1.8.0.1}
#   - {max: transwarp-5.1.0-final, min: transwarp-5.1.0-final}
#   release_name: tdc-1.0.0-rc1
# - products:
#   - {max: tos-1.8.0-rc2, min: tos-1.8.0-rc2}
#   - {max: transwarp-5.1.0-final, min: transwarp-5.1.0-final}
#   release_name: tdc-1.0.0-rc2
# ************************
from .config import verminator_config as VC
from .utils import *

__all__ = ['ProductReleaseMeta']


class ProductReleaseMeta(object):
    """ Processing `releases_meta.yaml`.
    """

    def __init__(self, yaml_file):
        with open(yaml_file) as ifile:
            self._raw_data = yaml.load(ifile)
        self._releases = self._load_releases()  # {tdc_release_ver: product: (minv, maxv)}
        self._major_versioned_releases = self._load_releases(True)

    @property
    def releases(self):
        return self._releases

    @property
    def major_versioned_releases(self):
        return self._major_versioned_releases

    def _load_releases(self, major_versioned=False):
        """ Read releases meta info of product lines
        """
        res = dict()

        for r in self._raw_data.get('Releases', list()):
            release_ver = parse_version(r.get('release_name'), major_versioned)
            if release_ver not in res:
                res[release_ver] = {}

            products = r.get('products', list())
            for p in products:
                minv = parse_version(p.get('min'), major_versioned)
                maxv = parse_version(p.get('max'), major_versioned)
                minv_name = product_name(minv)
                maxv_name = product_name(maxv)
                assert minv_name == maxv_name, \
                    'Product version should have the same prefix name: %s vs. %s' \
                    % (minv_name, maxv_name)

                pname = product_name(minv)
                if pname not in res[release_ver]:
                    res[release_ver][pname] = (minv, maxv)
                else:
                    vrange = res[release_ver][pname]
                    res[release_ver][pname] = concatenate_vranges(
                        [vrange, (minv, maxv)],
                        hard_merging=major_versioned
                    )[0]

        return res

    def get_tdc_version_range(self, version=None):
        """Get the tdc (complete) version range given a specific
        product version or None.
        """
        sorted_tdc_version = sorted(self._releases.keys(), key=cmp_to_key(
            lambda x, y: x.compares(y)
        ))
        if version is None:
            return sorted_tdc_version[0], sorted_tdc_version[-1]

        # Get compatible tdc versions in a normalized way
        version = parse_version(version)
        cv = self.get_compatible_versions(version)
        versions = list()  # [(minv, maxv)]
        for v1, v2 in cv.get(VC.OEM_NAME, list()):
            if is_major_version(v1):
                minv, maxv = None, None
                for v in sorted_tdc_version:
                    if v1 == to_major_version(v):
                        minv = v
                for v in sorted_tdc_version[::-1]:
                    if v2 == to_major_version(v):
                        maxv = v
                if None in (minv, maxv):
                    raise ValueError('Can not get valid tdc version range for {}'.format(version))
                versions.append((minv, maxv))
            else:
                versions.append((v1, v2))

        if len(versions) > 0:
            return versions[0][0], versions[-1][1]
        else:
            return None

    def get_compatible_versions(self, version):
        """ Given a product line name and a specific version,
        return the compatible product version ranges.
        """
        version = parse_version(version)
        product = product_name(version)

        # Check that the version is complete or in major form
        _is_major_version = is_major_version(version)
        releases = self._major_versioned_releases \
            if _is_major_version else self._releases

        derived_constraints = {
            product: [(version, version)]
        }
        declared_constraints = {}

        for r, products in releases.items():
            rp = product_name(r)
            if product != rp:
                # Derived
                if product not in products or \
                        not version.in_range(products[product][0], products[product][1]):
                    continue

                if rp not in derived_constraints:
                    derived_constraints[rp] = list()
                derived_constraints[rp].append((r, r))

                for p, vrange in products.items():
                    if p == product:
                        continue
                    if p not in derived_constraints:
                        derived_constraints[p] = list()
                    derived_constraints[p].append(vrange)
            else:
                # Declared maybe
                if r == version:
                    if rp not in declared_constraints:
                        declared_constraints[rp] = list()
                    declared_constraints[rp].append((r, r))
                    for p, vrange in products.items():
                        if p == product:
                            continue
                        if p not in declared_constraints:
                            declared_constraints[p] = list()
                        declared_constraints[p].append(vrange)
                else:
                    # Omit non-equal declared versions
                    pass

        # Merge the declared and derived.
        # In our algorithm, the declared releases represent the strong
        # dependencies between product lines such as sophon against tdh.
        # The derived represents the loose dependencies deduced from declared
        # releases such as tdc against sophon.
        merged = dict()
        keys = set(list(declared_constraints.keys()) + list(derived_constraints.keys()))
        for k in keys:
            declared = derived = None
            if k in declared_constraints:
                declared = concatenate_vranges(declared_constraints[k], hard_merging=_is_major_version)
            if k in derived_constraints:
                derived = concatenate_vranges(derived_constraints[k], hard_merging=_is_major_version)

            if derived is None and declared is None:
                continue
            elif derived is not None and declared is None:
                merged[k] = derived
            elif derived is None and declared is not None:
                merged[k] = declared
            else:
                # Filter derived by declared
                merged[k] = list()
                for v in derived:
                    for w in declared:
                        f = filter_vrange(v, w)
                        if f is not None:
                            v = f
                    if v is not None:
                        merged[k].append(v)

        return merged
