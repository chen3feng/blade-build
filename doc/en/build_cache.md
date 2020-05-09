# Build Cache

## Incremental build
The Blade build is incremental and will only build the appropriate targets and their dependencies if they need to be updated. `clean` is usually not needed.

## Dedicated build cache system
The blade supports ccache, which can greatly speed up the rebuild.
If you specify the ccache directory by configuring the CCACHE_DIR environment variable, multiple workspaces of the same code base of the same user or multiple users can share the build cache.
For details, please refer to [related documents] (https://ccache.dev/manual/3.7.9.html#_sharing_a_cache), we also provide a [auxiliary tool] (../../tool/setup-shared-ccache.py) for easy setup.
