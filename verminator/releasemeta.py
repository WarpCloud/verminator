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

    DEFAULT_INSTANCE_NAME = None

    def __init__(self, yaml_file):
        with open(yaml_file) as ifile:
            self._raw_data = yaml.load(ifile, Loader=yaml.FullLoader)
        # -----------------------------------------------------------
        # Hierarchical version constraints, including:
        # * TDC release constraints on other product versions;
        # * Product release constraints on others else;
        # * Instance release constraints on other product versions;
        #
        # Inner data structure:
        # * {instance_name: release_ver: product_line: (minv, maxv)}
        # -----------------------------------------------------------
        self._releases = self._load_releases()
        self._major_versioned_releases = self._load_releases(True)

    def _load_releases(self, major_versioned=False):
        """ Read releases meta info of product lines
        """
        all_releases = dict()

        for r in self._raw_data.get('Releases', list()):

            # Extract release meta info.
            instance_name = r.get('instance', self.DEFAULT_INSTANCE_NAME)
            release_ver = parse_version(r.get('release_name'), major_versioned)
            if instance_name not in all_releases:
                all_releases[instance_name] = dict()
            if release_ver not in all_releases[instance_name]:
                all_releases[instance_name][release_ver] = dict()

            versioned_releases = all_releases[instance_name][release_ver]

            # Extract product constraints for each release version
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
                if pname not in versioned_releases:
                    versioned_releases[pname] = (minv, maxv)
                else:
                    vrange = versioned_releases[pname]
                    versioned_releases[pname] = concatenate_vranges(
                        [vrange, (minv, maxv)],
                        hard_merging=major_versioned
                    )[0]

        return all_releases

    def get_releases(self, instance_name=None):
        """
        Get all versioned releases for specific instance_name.

        :param instance_name: the specific instance name or None if not present.
        :return: {release_ver: product_line: (minv, maxv)} or empty dict.
        """
        return self._releases.get(instance_name, dict())

    def get_major_versioned_releases(self, instance_name=None):
        """
        Get all major versioned releases for specific instance_name.

        :param instance_name: the specific instance name or None if not present.
        :return: {release_ver: product_line: (minv, maxv)} or empty dict.
        """
        return self._major_versioned_releases.get(instance_name, dict())

    def get_tdc_version_range(self, version=None, instance_name=None):
        """Given a specific product version,
        :return: the compatible tdc (complete) version range, (minv, maxv)
        """
        tdc_versions = [i for i in self.get_releases(instance_name).keys()
                        if product_name(i) == VC.OEM_NAME]
        sorted_tdc_version = sorted(tdc_versions, key=cmp_to_key(
            lambda x, y: x.compares(y)
        ))

        rv1 = rv2 = None
        if version is None:
            rv1, rv2 = sorted_tdc_version[0], sorted_tdc_version[-1]
        else:
            # Get compatible tdc versions in a normalized way
            version = parse_version(version)

            # Get product-versions mapping
            pvmap = self.get_compatible_versions(version, True, instance_name)

            versions = list()  # [(minv, maxv)]
            for v1, v2 in pvmap.get(VC.OEM_NAME, list()):
                if is_major_version(v1):
                    minv, maxv = None, None
                    for v in sorted_tdc_version:
                        if v1 == to_major_version(v):
                            minv = v
                            break
                    for v in sorted_tdc_version[::-1]:
                        if v2 == to_major_version(v):
                            maxv = v
                            break
                    if None in (minv, maxv):
                        raise ValueError('Can not get valid tdc version range for {}'.format(version))
                    versions.append((minv, maxv))
                else:
                    versions.append((v1, v2))

            if len(versions) > 0:
                rv1, rv2 = versions[0][0], versions[-1][1]

        return None if None in (rv1, rv2) else (rv1, rv2)

    def get_compatible_versions(self, version, minor_versioned=False, instance_name=None):
        """
        Given a specific product version. If the instance_name is present,
        more constraints on the instance would be considered.
        Otherwise, the instance-specific constraints would be ignored.

        :param version: the product version.
        :param minor_versioned: if checking minor versions only.
        :param instance_name: the specified instance name.
        :return: the compatible product version ranges, {product: [(minv, maxv)]}
        """
        version = parse_version(version)
        product = product_name(version)

        # Check that the version is complete or in major form
        _is_major_version = is_major_version(version)
        instance_releases = dict()
        default_releases = dict()

        # Prepare instance-specific and default release meta info.
        if not _is_major_version or minor_versioned:
            default_releases = self.get_releases()
        else:
            default_releases = self.get_major_versioned_releases()

        if instance_name is not None:
            if not _is_major_version or minor_versioned:
                instance_releases = self.get_releases(instance_name=instance_name)
            else:
                instance_releases = self.get_major_versioned_releases(instance_name=instance_name)

        # Unify instance-specific and default release meta info, if present
        releases = default_releases
        for r, product_versions in instance_releases.items():
            if r not in releases:
                releases[r] = product_versions
            else:
                default_product_versions = releases[r]
                for p, vrange in product_versions.items():
                    # Filter default product version range with declared ones, forcedly
                    filtered = filter_vrange(default_product_versions[p], vrange)

                    assert filtered is not None, \
                        'Warning: version declaration conflicts for {}: {} and {}, please fix releases_meta.yml' \
                            .format(r, default_product_versions[p], vrange)

                    default_product_versions[p] = filtered

        # Differentiate derived and declared constraints
        derived_constraints = {}
        declared_constraints = {
            product: [(version, version)]  # We treat the input as declared constraint
        }

        def add_constraint(store, product, vrange):
            if product not in store:
                store[product] = list()
            store[product].append(vrange)

        # Construct constraints
        for r, product_versions in releases.items():
            pname = product_name(r)

            # Classify candidates as DECLARED if the target product is in the releases,
            # otherwise as DERIVED.
            if product == pname:  # DECLARED
                if r == version:  # Matched declared version
                    # Update constraints
                    add_constraint(declared_constraints, pname, (r, r))
                    for p, vrange in product_versions.items():
                        add_constraint(declared_constraints, p, vrange)

            else:  # DERIVED
                # Omit mismatched product-line
                # We assume the derived are concluded from EXPLICIT dependencies.
                # Then we always have no derived constraints for third-party instances,
                # because instance-specific constraints are not supported yet.
                if product not in product_versions:
                    continue

                if not _is_major_version:
                    if not version.in_range(product_versions[product][0], product_versions[product][1]):
                        continue  # Omit version range not containing target minor version
                else:
                    vmin, vmax = product_versions[product]
                    if not version.in_range(to_major_version(vmin), to_major_version(vmax)):
                        continue

                # Update constraints
                add_constraint(derived_constraints, pname, (r, r))
                for p, vrange in product_versions.items():
                    add_constraint(derived_constraints, p, vrange)

        # Merging constraints
        merged = self._merge_dd(declared_constraints, derived_constraints, _is_major_version)

        return merged

    def _merge_dd(self, declared_constraints, derived_constraints, hard_merging=False):
        """
        Merge both DECLARED and DERIVED constraints.

        In the merging algorithm, the DECLARED releasesz represent strong
        dependencies between product lines, which takes more priority
        than the DERIVED ones.

        :param declared_constraints: {product: [(minv, maxv)]}
        :param derived_constraints: {product: [(minv, maxv)]}
        :return: the merged product version ranges, {product: [(minv, maxv)]}
        """
        merged = dict()
        keys = set(list(declared_constraints.keys()) + list(derived_constraints.keys()))
        for k in keys:
            declared = derived = None
            if k in declared_constraints:
                declared = concatenate_vranges(declared_constraints[k], hard_merging)
            if k in derived_constraints:
                derived = concatenate_vranges(derived_constraints[k], hard_merging)

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
