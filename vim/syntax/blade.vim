" This is the Vim syntax file for Blaze.
" Author: Chen Feng <phongchen@tencent.com>
" Usage:
"
" 1. cp blade.vim ~/.vim/syntax/
" 2. Add the following to ~/.vimrc:
"
" augroup filetype
"   au! BufRead,BufNewFile BUILD setfiletype blade
" augroup end
"
" Or just create a new file called ~/.vim/ftdetect/blade.vim with the
" previous lines on it.

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

" Sorted by alphabet order
syn keyword bladeTarget cc_binary cc_library cc_plugin cc_test cc_benchmark cu_binary cu_library
syn keyword bladeTarget enable_if gen_rule lex_yacc_library proto_library java_jar
syn keyword bladeTarget resource_library swig_library

" Sorted by alphabet order
syn keyword bladeArg always_run cmd defs deprecated deps dynamic_link export_incs
syn keyword bladeArg exclusive export_dynamic extra_cppflags extra_linkflags
syn keyword bladeArg heap_check heap_check_debug incs link_all_symbols
syn keyword bladeArg name optimize outs prebuilt prefix srcs suffix testdata warning

if version >= 508 || !exists("did_blade_syn_inits")
    if version < 508
        let did_blade_syn_inits = 1
        command! -nargs=+ HiLink hi link <args>
    else
        command! -nargs=+ HiLink hi def link <args>
    endif

    HiLink bladeTarget   Function
    HiLink bladeArg      Special
    delcommand HiLink
endif

let b:current_syntax = "blade"

