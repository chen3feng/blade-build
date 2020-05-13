"""Public API for user rules"""

# Default imports for user code
import config
import console


def current_source_dir():
    """Get current source dir (in which the current BUILD resident) relative to WORKSPACE root"""
    import blade.build_manager
    return blade.build_manager.instance.get_current_source_path()


def current_target_dir():
    """Get corresponding target dir of current source dir, such as build64_release/xxx"""
    import os
    import blade.build_manager
    return os.path.join(blade.build_manager.instance.get_build_path(), current_source_dir())

