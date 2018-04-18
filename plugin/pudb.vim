" stub for any viml bindings I want to add
" grab a copy of the pudb breakpoint code for porting to vim8
" File: pudb.vim
" Author: Christophe Simonis
" Description: Manage pudb breakpoints directly into vim
" Last Modified: December 03, 2012
"
" This plugin is handled by python3 for neovim, so this script is only for
" vim8 with +terminal support ( has('terminal') )
if !has('nvim')
    if exists('g:loaded_pudb_plugin') || &cp
        finish
    endif
    let g:loaded_pudb_plugin = 1

    if !exists("g:pudb_python_launcher")
        let g:pudb_python_launcher='python'
    endif
    " TODO: move to command
    if !exists("g:pudb_entry_point")
        let g:pudb_entry_point='${HOME}/src/poweruser_tools/test/test_templates.py'
    endif
    if !exists("g:pudb_breakpoint_symbol")
        let g:pudb_breakpoint_symbol='!'
    endif
    if !exists("g:pudb_sign_name")
        let g:pudb_sign_name='pudbbp'
    endif
    if !exists("g:pudb_highlight_group")
        let g:pudb_highlight_group='debug'
    endif
    function! s:signid()
        return 10*vim.eval("getline('.')")
    endfunction
    execute 'sign' 'define' g:pudb_sign_name 'text='.g:pudb_breakpoint_symbol 'texthl='.g:pudb_highlight_group
    augroup pudbbp
        autocmd BufReadPost *.py call s:SetInitialBreakpoints()
    augroup end
    command! ToggleBreakPoint call s:ToggleBreakPoint()

    function! s:SetInitialBreakpoints()
    if !has("pythonx")
        echo "Error: Required vim compiled with +python"
        return
    endif
    if !exists("b:pudb_buffer_signs")
        let b:pudb_buffer_signs = []
    endif
    exec 'sign' 'unplace' '*' 'file='.expand("%:p")
    pythonx << EOF
import vim
import pudb
filename = vim.eval('expand("%:p")')
bps = pudb.settings.load_breakpoints()
for bp in bps:
    if bp[0] != filename:
        continue
    line = vim.eval('getline(".")')
    sign_id = 10 * line
    vim.command('sign place {} line={} name={} file={}'.format(
            sign_id,
            line,
            vim.eval('g:pudb_sign_name'),
            vim.eval('expand("%:p")')
        ))
    vim.eval('add(b:pudb_buffer_signs, {})'.format(sign_id))
EOF
    endfunction
    function! s:ToggleBreakPoint()
    if !has("pythonx")
        echo "Error: Required vim compiled with +python"
        return
    endif
    pythonx << EOF
import vim
import pudb
from bdb import Breakpoint
bps = [pudbbp[:2] for pudbbp in pudb.settings.load_breakpoints()]
bp = (vim.eval('expand("%:p")'), vim.current.window.cursor[0])
if bp in bps:
    bps.pop(bps.index(bp))
else:
    bps.append(bp)
pudb.settings.save_breakpoints([Breakpoint(bp[0], bp[1]) for bp in bps])
EOF
    call s:SetInitialBreakpoints()
    endfunction
    command! LaunchDebuggerTab call s:LaunchDebugger()
    function! s:LaunchDebugger()
        execute 'tab' 'terminal' '++close' g:pudb_python_launcher g:pudb_entry_point
    endfunction
endif
