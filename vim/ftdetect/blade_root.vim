" This is the Vim filetype detect script for Blade.
" Author: Yafei Zhang <kimmyzhang@tencent.com>

augroup filetype
    autocmd! BufRead,BufNewFile .bladerc,blade.conf,BLADE_ROOT,BLADE_ROOT.local set filetype=blade_config
augroup end
