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
from .utils import *
from .config import VerminatorConfig as VC

__all__ = ['ProductReleaseMeta']


class ProductReleaseMeta(object):
    """ Processing `releases_meta.yaml`.
    """

    def __init__(self, yaml_file):
        self._raw_data = yaml.load(open(yaml_file))
        self._releases = self._load_releases()
        self._minor_versioned_releases = self._load_releases(True)

    @property
    def releases(self):
        return self._releases

    @property
    def minor_versioned_releases(self):
        return self._minor_versioned_releases

    def _load_releases(self, minor_versioned_only=False):
        """ Read releases meta info of product lines
        """
        res = dict()  # {release_name: product: (minv, maxv)}

        for r in self._raw_data.get('Releases', list()):
            rname = parse_version(r.get('release_name'), minor_versioned_only)

            if rname not in res:
                res[rname] = dict()

            products = r.get('products', list())
            for p in products:
                minv = parse_version(p.get('min'), minor_versioned_only)
                maxv = parse_version(p.get('max'), minor_versioned_only)
                minv_name = get_product_name(minv)
                maxv_name = get_product_name(maxv)
                assert minv_name == maxv_name, \
                    'Product version should have the same prefix name: %s vs. %s' \
                    % (minv_name, maxv_name)

                pname = get_product_name(minv)
                if pname not in res[rname]:
                    res[rname][pname] = (minv, maxv)
                else:
                    vrange = res[rname][pname]
                    res[rname][pname] = concatenate_vranges(
                        [vrange, (minv, maxv)],
                        hard_merging=minor_versioned_only
                    )[0]

        return res

    def get_compatible_versions(self, version):
        """ Given a product line name and a specific version,
        return the compatible product version ranges.
        """
        res = dict()  # {product: [(minv, maxv), (minv, maxv)]}

        version = parse_version(version)
        product = get_product_name(version)

        minor_versioned_only = is_minor_versioned_only(version)
        releases = self._minor_versioned_releases \
            if minor_versioned_only else self._releases

        if product == VC.OEM_NAME:
            if version not in releases:
                raise ValueError('Version %s should be declared in releasemeta' % version)

            products = releases[version]
            for pname, vrange in products.items():
                res[pname] = [vrange]
        else:
            res[VC.OEM_NAME] = list()
            for rname, products in releases.items():

                if product not in products:
                    # Ignore release without target product
                    continue

                minv, maxv = products.get(product)
                if not FlexVersion.in_range(version, minv, maxv):
                    # Ignore release not containing target version
                    continue

                # Remember TDC versions
                res[VC.OEM_NAME] = concatenate_vranges(
                    res[VC.OEM_NAME] + [(rname, rname)],
                    hard_merging=minor_versioned_only
                )

                # Extract other product versions
                for pname, vrange in products.items():
                    if pname == product:
                        continue
                    if pname not in res:
                        res[pname] = list()
                    res[pname] = concatenate_vranges(
                        res[pname] + [vrange],
                        hard_merging=minor_versioned_only
                    )

        # Remember the product per se
        res[product] = [(version, version)]

        return res
