from functools import cmp_to_key

from flex_version import FlexVersion, VersionMeta, VersionDelta


def parse_version(version):
    if not isinstance(version, VersionMeta):
        return FlexVersion.parse_version(version)
    return version


def get_product_name(version):
    version = parse_version(version)
    return version.prefix


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


def is_valid_final(version):
    version = parse_version(version)
    return True if version.suffix is not None else False


def get_compatible_versions(product_release_meta, version):
    """ Given a product line name and a specific version,
    return the compatible product version ranges.
    """
    res = dict()  # {product: [(minv, maxv), (minv, maxv)]}

    version = parse_version(version)
    product = get_product_name(version)

    if product == 'tdc':
        sv = str(version)
        if sv not in product_release_meta.releases:
            raise ValueError('Version %s not found' % sv)

        products = product_release_meta.releases[sv]
        for pname, vrange in products.items():
            res[pname] = [vrange]
    else:
        res['tdc'] = list()
        filetered_products = list()
        for rname, products in product_release_meta.releases.items():
            if product not in products:
                # Ignore release without target product
                continue
            minv, maxv = products.get(product)
            if not FlexVersion.in_range(version, minv, maxv):
                # Ignore release not containing target version
                continue
            # Remember TDC versions
            res['tdc'] = concatenate_version_ranges(
                res['tdc'] + [(rname, rname)]
            )
            # Extract other product versions
            for pname, vrange in products.items():
                if pname == product:
                    continue
                if pname not in res:
                    res[pname] = list()
                res[pname] = concatenate_version_ranges(
                    res[pname] + [vrange]
                )
    return res


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

        # Ranges between final and rc
        delta = cmin.substitute(pmax, ignore_suffix=True)
        if delta >= VersionDelta.zero and pmax.suffix == 'final':
            res[-1] = (pmin, cmax)
            continue

        res.append(vrange)

    return res
