" This is the Vim filetype detect script for Blade.
" Author: Chen Feng <phongchen@tencent.com>

augroup filetype
    autocmd! BufRead,BufNewFile BUILD,*.bld set filetype=blade
augroup end
