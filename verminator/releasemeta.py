from ruamel.yaml import YAML

from .utils import *

__all__ = ['ProductReleaseMeta']


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
            rname = parse_version(r.get('release_name'))
            assert rname not in self.releases, \
                'Duplicated release meta %s' % rname

            self.releases[rname] = dict()

            products = r.get('products', list())
            for p in products:
                minv = parse_version(p.get('min'))
                maxv = parse_version(p.get('max'))
                minv_name = get_product_name(minv)
                maxv_name = get_product_name(maxv)
                assert minv_name == maxv_name, \
                    'Product version should have the same prefix name: %s vs. %s' \
                    % (minv_name, maxv_name)

                pname = get_product_name(minv)
                assert pname not in self.releases[rname], \
                    'Duplicated product %s in release %s' % (pname, rname)
                self.releases[rname][pname] = (minv, maxv)
