# Cache system

## Incremental build
The Blade build is incremental and will only build the appropriate targets and their dependencies if they need to be updated. Clean is usually not needed.

## Dedicated build cache system
The blade supports ccache, which can greatly speed up the rebuild.
If you specify the ccache directory by configuring the CCACHE_DIR environment variable, the build cache can be shared between multiple workspaces or multiple users of the same user's same code base.
