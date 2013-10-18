" This is the Vim filetype detect script for Blaze.
" put it into you ~/.vim/ftdetect/
" Author: Chen Feng <phongchen@tencent.com>

augroup filetype
    autocmd! BufRead,BufNewFile BUILD setfiletype blade
augroup end

