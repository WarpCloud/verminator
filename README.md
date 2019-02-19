# Verminator

TDC image Version control tERMINATOR.

## Install

Requires Python 3.5+

```bash
pip install verminator -i http://172.16.1.161:30033/repository/pypi/simple/ --trusted-host=172.16.1.161
```

## Usage

**First, review product version ranges in `/path/to/product-meta/instances/releases_meta.yaml`**

### Validate instance releases

```bash
verminator validate /path/to/product-meta/instances
```

For specific instance, say inceptor

```bash
verminator validate -c inceptor /path/to/product-meta/instances
```

### Create a new OEM

```bash
verminator createoem -o gzes /path/to/product-meta/instances
```

### Create a new version

New version of a product line, say `sophon`
```bash
verminator createversion -p sophon-2.2.0-final /path/to/product-meta/instances

# Or based on a specific previous version
verminator createversion -p "sophon-1.3.0-final >>> sophon-2.2.0-final" /path/to/product-meta/instances
```

New version of a component, say `inceptor`
```bash
verminator createversion -c redis=4.0.0 /path/to/product-meta/instances

# Or based on a specific previous version
verminator createversion -c "redis=3.1.0 >>> redis=4.0.0" /path/to/product-meta/instances
```
