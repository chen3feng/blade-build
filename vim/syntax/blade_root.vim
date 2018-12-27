" This is the Vim syntax file for Blade.
" Author: Yafei Zhang <kimmyzhang@tencent.com>

if version < 600
    syntax clear
elseif exists("b:current_syntax")
    finish
endif

" Read the python syntax to start with
if version < 600
    so <sfile>:p:h/python.vim
else
    runtime! syntax/python.vim
    unlet b:current_syntax
endif

syn case match

syn keyword bladeTarget build_target
syn keyword bladeArg bits
syn keyword bladeArg arch
syn keyword bladeArg is_debug
syn keyword bladeTarget global_config
syn keyword bladeArg build_path_template
syn keyword bladeArg duplicated_source_action
syn keyword bladeArg test_timeout
syn keyword bladeArg native_builder
syn keyword bladeTarget cc_test_config
syn keyword bladeArg dynamic_link
syn keyword bladeArg heap_check
syn keyword bladeArg gperftools_libs
syn keyword bladeArg gperftools_debug_libs
syn keyword bladeArg gtest_libs
syn keyword bladeArg gtest_main_libs
syn keyword bladeArg pprof_path
syn keyword bladeTarget cc_binary_config
syn keyword bladeArg extra_libs
syn keyword bladeArg run_lib_paths
syn keyword bladeTarget distcc_config
syn keyword bladeArg enabled
syn keyword bladeTarget link_config
syn keyword bladeArg link_on_tmp
syn keyword bladeArg enable_dccc
syn keyword bladeTarget java_config
syn keyword bladeArg version
syn keyword bladeArg source_version
syn keyword bladeArg target_version
syn keyword bladeArg maven
syn keyword bladeArg maven_central
syn keyword bladeArg warnings
syn keyword bladeArg source_encoding
syn keyword bladeArg java_home
syn keyword bladeTarget java_binary_config
syn keyword bladeArg one_jar_boot_jar
syn keyword bladeTarget java_test_config
syn keyword bladeArg junit_libs
syn keyword bladeArg jacoco_home
syn keyword bladeArg coverage_reporter
syn keyword bladeTarget scala_config
syn keyword bladeArg scala_home
syn keyword bladeArg target_platform
syn keyword bladeArg warnings
syn keyword bladeArg source_encoding
syn keyword bladeTarget scala_test_config
syn keyword bladeArg scalatest_libs
syn keyword bladeTarget go_config
syn keyword bladeArg go
syn keyword bladeArg go_home
syn keyword bladeTarget thrift_config
syn keyword bladeTarget thrift_library_config
syn keyword bladeArg thrift
syn keyword bladeArg thrift_libs
syn keyword bladeArg thrift_incs
syn keyword bladeTarget fbthrift_config
syn keyword bladeTarget fbthrift_library_config
syn keyword bladeArg fbthrift1
syn keyword bladeArg fbthrift2
syn keyword bladeArg fbthrift_libs
syn keyword bladeArg fbthrift_incs
syn keyword bladeTarget proto_library_config
syn keyword bladeArg protoc
syn keyword bladeArg protoc_java
syn keyword bladeArg protobuf_libs
syn keyword bladeArg protobuf_path
syn keyword bladeArg protobuf_incs
syn keyword bladeArg protobuf_java_incs
syn keyword bladeArg protobuf_php_path
syn keyword bladeArg protoc_php_plugin
syn keyword bladeArg protobuf_java_libs
syn keyword bladeArg protobuf_python_libs
syn keyword bladeArg protoc_go_plugin
syn keyword bladeArg protobuf_go_path
syn keyword bladeArg protoc_direct_dependencies
syn keyword bladeArg well_known_protos
syn keyword bladeTarget cc_config
syn keyword bladeArg extra_incs
syn keyword bladeArg cppflags
syn keyword bladeArg cflags
syn keyword bladeArg cxxflags
syn keyword bladeArg arflags
syn keyword bladeArg ranlibflags
syn keyword bladeArg linkflags
syn keyword bladeArg c_warnings
syn keyword bladeArg cxx_warnings
syn keyword bladeArg warnings
syn keyword bladeArg cpplint
syn keyword bladeArg optimize
syn keyword bladeArg benchmark_libs
syn keyword bladeArg benchmark_main_libs
syn keyword bladeArg securecc
syn keyword bladeArg header_inclusion_dependencies
syn keyword bladeTarget cc_library_config
syn keyword bladeArg generate_dynamic
syn keyword bladeArg prebuilt_libpath_pattern
syn keyword bladeTarget protoc_plugin
syn keyword bladeArg name
syn keyword bladeArg path
syn keyword bladeArg code_generation


if version >= 508 || !exists("did_blade_roor_syn_inits")
    if version < 508
        let did_blade_root_syn_inits = 1
        command! -nargs=+ HiLink hi link <args>
    else
        command! -nargs=+ HiLink hi def link <args>
    endif

    HiLink bladeTarget   Function
    HiLink bladeArg      Special
    delcommand HiLink
endif

let b:current_syntax = "blade_root"
