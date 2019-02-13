from functools import cmp_to_key

from flex_version import FlexVersion, VersionMeta, VersionDelta

# Customized version suffix ordering
FlexVersion.ordered_suffix = ['rc', 'final', None]


def parse_version(version, minor_versioned_only=False):
    if not isinstance(version, VersionMeta):
        version = FlexVersion.parse_version(version)

    if minor_versioned_only:
        version.maintenance = None
        version.build = None
        version.suffix = None
        version.suffix_version = None

    return version


def get_product_name(version):
    version = parse_version(version)
    return version.prefix


def is_minor_versioned_only(version):
    version = parse_version(version)
    return version.maintenance is None \
        and version.build is None \
        and version.suffix is None \
        and version.suffix_version is None


def filter_vrange(this, other):
    cmin, cmax = this
    omin, omax = other

    if get_product_name(cmin) == get_product_name(omin):
        if omin is not None:
            cmin = cmin if omin <= cmin else omin if omin < cmax else None
        if omax is not None:
            cmax = cmax if omax >= cmax else omax if omax > cmin else None

    if None in (cmin, cmax):
        return None
    else:
        return (cmin, cmax)


def concatenate_vranges(vranges, hard_merging=False):
    """ Connect and merge version ranges.
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
