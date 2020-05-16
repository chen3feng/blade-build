#!/usr/bin/env python


"""About main entry

Main entry is placed to __main__.py, cause we need to pack
the python sources to a zip ball and invoke the blade through
command line in this way: python blade.zip

"""


import sys
from blade.blade_main import main


if __name__ == '__main__':
    sys.exit(main(sys.argv[0], sys.argv[1:]))
