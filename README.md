# PUDB Integration with NeoVim 
#### *(Vim8 support for :terminal coming soon!)*
### Integration between vim8/neovim and pudb.

### Adds new commands:
* **PUDBToggleBreakPoint** - Toggles a breakpoint on the current line (requires ft=python)
* **PUDBClearAllBreakpoints** - Clears all currently set breakpoitns on the current file (requires ft=python)
* **PUDBUpdateBreakPoints** - Updates any breakpoints set outside of neovim (such as in the debugger itself)
* **PUDBStatus** - Shows a status printout (in `:messages`) for the plugin
> **Note**: while most of these commands are common between Vim8 and neovim, the PudbStatus command is only in NeoVim.  This is because NeoVim has rplugin instance objects that retain state (more efficient and powerful) but vim8 plugins use inline python and can't retain state.
* **PUDBLaunchDebuggerTab** - Launches pudb in a new tab.
> **Note**: Vim8 support at least partly broken in tmux and MacVim, most probably because of how they are setting up the TERM settings.
* **PUDBSetEntrypointVENV**: Sets both the entrypoint (script to be run) and the python to use (virtual environment) if it can be determined.  This can be very important for breakpoints as well, as different virtual environments will have different PUDB debuggers and possibly different lists of breakpoints.  Make sure you call `:PUDBUpdateBreakPoints` on any file after changing the launcher.  If you merely toggle a breakpoint then any other breakpoints will be written out to pudb using the current buffer.
* **PUDBSetEntrypoint**: Sets only the entrypoint (script to be run) when you launch the debugger.  Useful if your breakpoint is in a different file.


### Accepts options configuration variables:
* `pudb_python` - Which python to use to launch pudb.  Can integrate with virtualenvs.
* `pudb_entry_point` - Which script to use to 'enter' your program in debug mode.  If not set, the current buffer will be used.
* `pudb_breakpoint_symbol` - The symbol representation

For example:
```vim
" Nvim python environment settings
if has('nvim')
  let g:python_host_prog='~/.virtualenvs/neovim2/bin/python'
  let g:python3_host_prog='~/.virtualenvs/neovim3/bin/python'
  " set the virtual env python used to launch the debugger
  let g:pudb_python='~/.virtualenvs/poweruser_tools/bin/python'
  " set the entry point (script) to use for pudb
  let g:pudb_entry_point='~/src/poweruser_tools/test/test_templates.py'
  " Unicode symbols work fine (nvim, iterm, tmux, nyovim tested)
  let g:pudb_breakpoint_symbol='☠'
endif
```

> **Note**: The last time I checked relative paths `~/.config/` aren't working for the host_prog properties.  I may take a look at neovim's code and try to find out why in the future.  They do work for the rplugin, however, as it uses os.path.expanduser on any rc file paths.  I haven't yet gotten to that part in the vimscript for vim8, so I may find it more difficult to do with regular plugins.


### Usage Video:
![quick usage example](doc/quickdemo.gif)
