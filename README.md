# PUDB Integration with NeoVim
    Integration between neovim and pudb.

### Adds new commands:
    * ToggleBreakPoint - Toggles a breakpoint on the current line (requires ft=python)
    * ClearAllBreakpoints - Clears all currently set breakpoitns on the current file (requires ft=python)
    * UpdateBreakPoints - Updates any breakpoints set outside of neovim (such as in the debugger itself)
    * PudbStatus - Shows a status printout (in `:messages`) for the plugin
    * LaunchDebuggerTab - Launches pudb in a new tab.

### Accepts options configuration variables:
    * `pudb_python` - Which python to use to launch pudb.  Can integrate with virtualenvs.
    * `pudb_entry_point` - Which script to use to 'enter' your program in debug mode.  If not set, the current buffer will be used.

For example:
```vim
" Nvim python environment settings
if has('nvim')
  let g:python_host_prog='${HOME}/.virtualenvs/neovim2/bin/python'
  let g:python3_host_prog='${HOME}/.virtualenvs/neovim3/bin/python'
  " set the virtual env python used to launch the debugger
  let g:pudb_python='${HOME}/.virtualenvs/poweruser_tools/bin/python'
  " set the entry point (script) to use for pudb
  let g:pudb_entry_point='${HOME}/src/poweruser_tools/test/test_templates.py'
endif
```

> Note: Do not actually use `${HOME}` in `g:python_host_prog` or `g:python3_host_prog` as this will confuse NeoVim and cause it to unload python and all rplugins.  I'm merely showing it here as an example

### Usage Video:
![quick usage example](doc/quickdemo.gif)
