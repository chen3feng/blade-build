# Package Files #

Package file from source tree and build targets

Example:

```python
package(
    name = 'server_package',
    type = 'tgz',
    srcs = [
        # executable
        ('$(location //server:server)', 'bin/server'),
        # conf
        ('//server/conf/server.conf', 'conf/server.conf'),
    ]
)
```

`type` can be `zip`, `tar`, `tar.gz`, `tgz`, `tar.bz2`, `tbz`，`type` will also be the suffix of the result file.

Because generating the package is quiet slow, and they are rarely be used in the develop stage.
This rule does't run defaultly, `--generate-package` is required to enable it.
