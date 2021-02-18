# Some Tools Maybe Useful for You

- bladefunctions

  Some helpful shell functions, such as switch between source dir and target dir accordingly.

- fix-include-path.sh

  Automatically fix `#include` without full path in c/c++ files, and change it to the full path form.

- genlibbuild

  Assuming that the current directory is a C/C++ library, then generate the `BUILD` file of the
  library is automatically, and the library name is the directory name.
  If there are test files, the corresponding cc_test tests is automatically generated.

- lsnobuild

  List those directories that have `Makefile` but no `BUILD` files to assist projects that use
  recursive Make to migrate to Blade easily.

- lsrc

  List all C/C++ source files in the `srcs = [...]` format under current directory (excludes testing file such as `*_test.cc`)

- merge-static-libs

  Merge a blade library and all its transitive dependencies into a large static library.

- setup-shared-ccache.py

  Set up sharing ccache compilation cache between multiple users on a single machine.

- collect-hdrs-missing.py

  Collect the `cc_library.hdr` missing report and generate a suppress list.

- collect-disallowed-maven-jars.py

  Collect the disallowed `maven_jar`s due to the `java_config.maven_jar_allowed_dirs` restriction.

- collect-inclusion-errors.py

  Collect inclusion errors and report the summarized information.
