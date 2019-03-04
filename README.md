# Verminator

TDC image Version control tERMINATOR.

## Install

Requires Python 3.5+

```bash
pip3 install verminator -i http://172.16.1.161:30033/repository/pypi/simple/ --trusted-host=172.16.1.161
```

## Usage

**First, update product version ranges in `/path/to/product-meta/instances/releases_meta.yaml`**

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
verminator genoem -o gzes /path/to/product-meta/instances
```

### Create a new version

New version of a product line, say `sophon`
```bash
verminator genver -v sophon-2.2.0-final /path/to/product-meta/instances
```

For specific instance, say inceptor
```bash
verminator genver -c inceptor -v transwarp-6.0.1-final /path/to/product-meta/instances
```

### For OEM

If you are working on an OEM branch, make sure env `export OEM_NAME=xxx` set or command option `-o xxx` is given on the subcommand like `validate` and `genver`.