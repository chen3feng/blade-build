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

syn keyword bladeTarget cc_binary cc_library cc_plugin cc_test enable_if
syn keyword bladeTarget gen_rule lex_yacc_library proto_library java_jar
syn keyword resource_library swig_library

syn keyword bladeArg always_run cmd defs deprecated deps dynamic_link exclusive
syn keyword bladeArg extra_cppflags heap_check heap_check_debug incs
syn keyword bladeArg link_all_symbols name outs prebuilt srcs testdata warning

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

