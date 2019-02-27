import copy
from collections import OrderedDict
from functools import cmp_to_key

import yaml
from flex_version import FlexVersion, VersionMeta, VersionDelta

# Customized version suffix ordering
FlexVersion.ordered_suffix = ['rc', 'final', None]


def ordered_yaml_load(yaml_path, Loader=yaml.Loader,
                      object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    with open(yaml_path) as stream:
        return yaml.load(stream, OrderedLoader)


def ordered_yaml_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


def parse_version(version, major_versioned=False):
    if not isinstance(version, VersionMeta):
        version = FlexVersion.parse_version(version)
    else:
        version = copy.deepcopy(version)

    if major_versioned:
        version.maintenance = None
        version.build = None
        version.suffix = None
        version.suffix_version = None

    return version


def product_name(version):
    version = parse_version(version)
    return version.prefix


def replace_product_name(version, newname, by=None):
    version = parse_version(version)
    if by is not None and version.prefix == by:
        version.prefix = newname
    elif by is None:
        version.prefix = newname
    return version


def is_major_version(version):
    version = parse_version(version)
    return version.maintenance is None \
           and version.build is None \
           and version.suffix is None \
           and version.suffix_version is None


def to_major_version(version):
    version = parse_version(version)
    version.maintenance = None
    version.build = None
    version.suffix = None
    version.suffix_version = None
    return version


def filter_vrange(this, other):
    cmin, cmax = this
    omin, omax = other

    if product_name(cmin) == product_name(omin):
        if omin is not None:
            cmin = cmin if omin <= cmin else omin if omin < cmax else None
        if omax is not None:
            cmax = cmax if omax >= cmax else omax if omax > cmin else None

    if None in (cmin, cmax):
        return None
    else:
        return (cmin, cmax)


def concatenate_vranges(vranges, hard_merging=False):
    prefixes = dict()
    for vrange in vranges:
        prefix = vrange[0].prefix
        if prefix not in prefixes:
            prefixes[prefix] = list()
        prefixes[prefix].append(vrange)

    concatenated = [_concatenate_vranges_with_same_prefix(vranges, hard_merging) \
                    for vranges in prefixes.values()]
    return [y for x in concatenated for y in x]


def _concatenate_vranges_with_same_prefix(vranges, hard_merging=False):
    """ Connect and merge version ranges.
    @return a list of concatenated version ranges.
    """
    sorted_vranges = sorted(vranges, key=cmp_to_key(
        lambda x, y: FlexVersion.compares(x[0], y[0])
    ))

    res = [sorted_vranges[0]]
    for vrange in sorted_vranges[1:]:
        pmin, pmax = res[-1]
        cmin, cmax = vrange

        if not hard_merging:
            # Ranges connected directly:
            # * Overlapping ranges
            # * adjacent suffix versions
            if cmin.suffix is not None and pmin.suffix is not None:
                if cmin == pmax.add(VersionDelta(sver=1)):
                    res[-1] = (pmin, cmax)
                    continue
                else:
                    overlapped = pmin.in_range(cmin, cmax) \
                                 or pmax.in_range(cmin, cmax) \
                                 or cmin.in_range(pmin, pmax) \
                                 or cmax.in_range(pmin, pmax)
                    if overlapped:
                        minv = cmin if cmin < pmin else pmin
                        maxv = cmax if cmax > pmax else pmax
                        res[-1] = (minv, maxv)
                        continue

            # Ranges between rc and final
            if pmax.substitute(cmin, ignore_suffix=True) == VersionDelta.zero \
                    and pmax.suffix == 'rc' and cmin.suffix == 'final':
                res[-1] = (pmin, cmax)
                continue

            # Ranges between final and rc
            delta = cmin.substitute(pmax, ignore_suffix=True)
            if delta >= VersionDelta.zero and pmax.suffix == 'final':
                res[-1] = (pmin, cmax)
                continue

            # Strict concatenation policy
            res.append(vrange)
        else:
            res[-1] = (pmin, cmax)

    return res


if __name__ == '__main__':
    vranges = [
        (FlexVersion.parse_version('sophonweb-1.2.0-final'),
         FlexVersion.parse_version('sophonweb-2.2.0-final')),
        (FlexVersion.parse_version('sophonweb-1.3.0-rc0'),
         FlexVersion.parse_version('sophonweb-1.3.0-rc3'))
    ]
    print(concatenate_vranges(vranges))

    assert str(replace_product_name('tdc-1.2', 'gzes')) == 'gzes-1.2'
    assert str(replace_product_name('transwarp-1.2', 'gzes', by='tdc')) == 'transwarp-1.2'
    assert str(replace_product_name('tdc-1.2', 'gzes', by='tdc')) == 'gzes-1.2'
