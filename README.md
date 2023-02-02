# Blade Build System

[![license NewBSD](https://img.shields.io/badge/License-NewBSD-yellow.svg)](COPYING)
[![Python](https://img.shields.io/badge/language-python2,3-blue.svg)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-google-blue.svg)](https://google.github.io/styleguide/pyguide.html)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos-lightgrey.svg)](doc/en/prerequisites.md)

```
██████╗ ██╗      █████╗ ██████╗ ███████╗
██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝
██████╔╝██║     ███████║██║  ██║█████╗
██╔══██╗██║     ██╔══██║██║  ██║██╔══╝
██████╔╝███████╗██║  ██║██████╔╝███████╗
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
```

English | [简体中文](README-zh.md)

An easy-to-use, fast and modern build system for trunk based development in large-scale monorepo codebase.

## Build Status

[![Build Status](https://travis-ci.org/chen3feng/blade-build.svg?branch=master)](https://travis-ci.org/chen3feng/blade-build)
[![codebeat badge](https://codebeat.co/badges/e0d861b7-47cc-4023-9784-7d54246a3576)](https://codebeat.co/projects/github-com-chen3feng-blade-build-master)
[![Coverage](https://coveralls.io/repos/chen3feng/blade-build/badge.svg?branch=master)](https://coveralls.io/github/chen3feng/blade-build)
[![Downloads](https://img.shields.io/github/downloads/chen3feng/blade-build/total.svg)](https://github.com/chen3feng/blade-build/releases)

## Demo

First, let's see a cool demo:

[![asciicast](https://asciinema.org/a/o9uQ2uia4OVqghXUid7XSNjv1.svg)](https://asciinema.org/a/o9uQ2uia4OVqghXUid7XSNjv1)

## Releases

The code on the master branch is development version and should be considered as alpha version. 
Please prefer using the version on the tags in your formal environment.
We will release the verified version on the large-scale internal code base to the tag from time to time.

* Version 2.0 is in release candidate! It includes the following notable changes:

  * minimal python version 2.7, support python 3
  * Support Java, scala building
  * Full support to Python
  * Support custom extensions
  * Only use [ninja](doc/en/config.md#global_config) as backend build system, increases speed dramatically.

Please follow the [Upgrade Notes](doc/en/upgrade-to-v2.md) to upgrade.

## Stargazers over time

[![Stargazers over time](https://starchart.cc/chen3feng/blade-build.svg)](https://starchart.cc/chen3feng/blade-build)
      
## Brief

Blade is designed to be a modern build system. It is powerful and easy to use. It supports building
multiple languages, such as c/c++, java, python, scala, protobuf, etc. It analyzes the
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
* Simple command line interface similar to git/svn.
* Memory leak checking in tests(with gperftools).
* Bash command line completion.
* Colorful diagnostic message displaying.
* Vim integration, includes syntax highlighting, quick fix.

## Documentation

* [Full Documentation](doc/en/README.md)
* [FAQ](doc/en/FAQ.md)

## Contributers

[![Contributers](https://contrib.rocks/image?repo=chen3feng/blade-build)](https://github.com/chen3feng/blade-build/graphs/contributors)

## Credits

* Blade is inspired by Google's public information about their build system. Here is a reference article from Google's official blog:
  [build in cloud: how build system works](http://google-engtools.blogspot.hk/2011/08/build-in-cloud-how-build-system-works.html).

  Later in 2015, they released it with partial rewritten as `bazel` open-source build system.

* Blade generates [Ninja](https://ninja-build.org/) script internally, so of course it depends on ninja.
* [Python](http://www.python.org) is a powerful and easy-to-used language, we like python.
* Some libraries open sourced by Google, such as [protobuf](http://code.google.com/p/protobuf/),
* [gtest](http://code.google.com/p/googletest/),
* [gperftools](http://code.google.com/p/gperftools/) are handy and powerful, we have integrated these libraries.
