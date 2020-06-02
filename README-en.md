# Blade Build System

```
██████╗ ██╗      █████╗ ██████╗ ███████╗
██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝
██████╔╝██║     ███████║██║  ██║█████╗
██╔══██╗██║     ██╔══██║██║  ██║██╔══╝
██████╔╝███████╗██║  ██║██████╔╝███████╗
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
```

An easy-to-use, fast and modern build system for trunk based development in large scale monorepo codebase.

NOTE: The English Documentation is still under construction, sorry for the incompleteness.

## Build status

[![Build Status](https://travis-ci.org/chen3feng/blade-build.svg?branch=master)](https://travis-ci.org/chen3feng/blade-build)

## Brief

Blade is designed to be a modern build system. It is powerful and easy to use. It supports building
multiple languages, such as c/c++, java, python, scala, protobuf and swig etc. It analyzes the
target dependency automatically and integrates compiling, linking, testing(includes incremental
testing and parallel testing) and static code inspectiontogether.
It aims to improve the clarity and simplicity of the building rules for a project.

With Blade, you can compile, link and test multiple targets by just inputting one simple command line.
For example:

Build and test all targets in common directory recursively.

```bash
blade test common...
```

Build and test targets as 32 bit

```bash
blade test -m32 common...
```

Build and test targets as debug mode

``` bash
blade test -pdebug common...
```

And you can combine the flags together:

``` bash
blade test -m32 -pdebug common...
```

## Features

* Auto dependency analysis, includes header files and libraries.
* Test integration: built-in support of gtest. Support incremental testing and parallel testing.
* Simple syntax, easy to use.
* Simple command line interface similar to svn.
* Memory leak checking(with gperftools).
* Bash command line completion.
* Colorful diagnostic message displaying.
* Vim integration, includes syntax hi-light, quickfix.

## Documentation

Sorry for Chinese only, English documentation is under construction.

* [Full Documentation](/doc/en/index.md)
* [FAQ](/doc/en/FAQ.md)

## Credits

* Blade is inspired by Google's public information about their building system. Here is a reference article from Google's official blog.

[build in cloud: how build system works](http://google-engtools.blogspot.hk/2011/08/build-in-cloud-how-build-system-works.html)

* Blade generates [Ninja](https://ninja-build.org/) script internally, so of cause it depends on ninja.
* [Python](http://www.python.org) is a powerful and easy-to-used language, we like python.
* Some libraries open sourced by Google, such as [protobuf](http://code.google.com/p/protobuf/),
  [gtest](http://code.google.com/p/googletest/),
  [gperftools](http://code.google.com/p/gperftools/) are handy and powerful, we have integrated these libraries.
