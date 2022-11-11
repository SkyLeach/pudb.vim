'''
Python3 module for neovim to integrate with the most excellent pudb python
debugger in order to make neovim not only an excellent editor but also a
full-function python IDE.
'''
from bdb import Breakpoint
import logging
import pprint
import collections
import os
from typing import Dict, List
# all rplugin import
import neovim
# rplugin-specific
import pudb
__logger__ = logging.getLogger('pudb.vim')


class NvimOutLogHandler(logging.Handler):
    """NvimOutLogHandler
    python logging handler to output messages to the neovim user
    """

    def __init__(self, nvim, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nvim = nvim
        self._terminator = '\n'

    def emit(self, record):
        self._nvim.out_write(self.format(record))
        self._nvim.out_write(self._terminator)
        self.flush()


def signid(buffname, lineno):
    """signid
    returns the signid generated from the filename and line number
    :param buffname: name of the buffer (filename)
    :param lineno: line number specific to buffer
    """
    return 10 * lineno
    # return hash(buffname) + lineno


@neovim.plugin
class NvimPudb(object):
    """NvimPudb
    neovim rplugin class to manage pudb debugger from neovim code.
    """

    # @property
    def sgnname(self):
        return self.nvim.vars.get('pudb_sign_name', 'pudbbp')

    # @sgnname.setter
    def set_sgnname(self, sgnname):
        self.nvim.command("let g:pudb_sign_name='{}'".format(sgnname))

    # @property
    def bpsymbol(self):
        return self.nvim.vars.get('pudb_breakpoint_symbol', '!')

    # @bpsymbol.setter
    def set_bpsymbol(self, bpsymbol):
        self.nvim.command("let g:pudb_breakpoint_symbol='{}'".format(bpsymbol))

    # @property
    def hlgroup(self):
        return self.nvim.vars.get('pudb_highlight_group', 'debug')

    # @hlgroup.setter
    def set_lgroup(self, hlgroup):
        self.nvim.command("let g:pudb_highlight_group='{}'".format(hlgroup))

    # @property
    def launcher(self):
        return self.nvim.vars.get('pudb_python_launcher', self.nvim_python3())

    # @launcher.setter
    def set_launcher(self, launcher):
        self.nvim.command("let g:pudb_python_launcher='{}'".format(launcher))

    # @property
    def nvim_python(self):
        return self.nvim.vars.get('python_host_prog', 'python')

    # @property
    def nvim_python3(self):
        return self.nvim.vars.get('python3_host_prog', self.nvim_python())

    # @property
    def entrypoint(self):
        return self.nvim.vars.get('pudb_entry_point', self.cbname())

    # @entrypoint.setter
    def set_entrypoint(self, entrypoint):
        if self.nvim.vars.get('pudb_entry_point', None) != entrypoint:
            self.nvim.command("let g:pudb_entry_point='{}'".format(entrypoint))
        else:
            self.nvim.command("unlet g:pudb_entry_point")
            self.nvim.command("echo 'Entry point cleared'")

    # @property
    def cbname(self):
        """cbname
        returns the current buffer's name attribute
        """
        return self.nvim.current.buffer.name

    def __init__(self, nvim=None):
        # set our nvim hook first...
        self.nvim = nvim
        self._toggle_status = {}
        self._bps_placed = {}  # type: Dict[str,List]
        self._cond_dict = {}  # type: Dict[str,List]
        self._bp_config_dir = ""
        self._bp_file = ""
        self.load_base_dir()
        self.load_bp_file()
        # update the __logger__ to use neovim for messages
        nvimhandler = NvimOutLogHandler(nvim)
        # nvimhandler.setLevel(logging.INFO)
        nvimhandler.setLevel(logging.DEBUG)
        __logger__.setLevel(logging.DEBUG)
        __logger__.addHandler(nvimhandler)
        # define our sign command

    def place_sign(self, buffname, lineno):
        """place_sign
        Places a new sign on the buffer and registers it as a breakpoint with
        pudb
        :param buffname:
        :param lineno:
        """
        # do nothing without a line number
        if not lineno:
            return None
        # don't place it if it has already been placed
        if self.has_breakpoint(buffname, lineno):
            return self.pudbbp(buffname, lineno)
        if self.toggle_sign:
            signcmd = "sign place {} line={} name={} file={}".format(
                signid(buffname, lineno),
                lineno,
                self.sgnname(),
                buffname)
            self.nvim.command(signcmd)
        if buffname in self._bps_placed:
            self._bps_placed[buffname].append(signid(buffname, lineno))
        else:
            self._bps_placed[buffname] = [signid(buffname, lineno)]
        return self.pudbbp(buffname, lineno)

    def remove_sign(self, buffname, lineno):
        """remove_sign
        removes the sign from the buffer and the breakpoint from pudb
        :param buffname:
        :param bpt:
        """
        if not self.has_breakpoint(buffname, lineno):
            return
        if self.toggle_sign:
            vimmsg = 'sign unplace {} file={}'.format(
                signid(buffname, lineno),
                buffname)
            self.nvim.command(vimmsg)
        self._bps_placed[buffname].pop(
            self._bps_placed[buffname].index(
                signid(buffname, lineno)))

    @neovim.command("PUDBClearAllBreakpoints", sync=False)
    def clear_all_bps(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.test_buffer(buffname)
        for num_line in self._bps_placed[buffname]:
            self.remove_sign(buffname, num_line)
        self._bps_placed[buffname] = []
        self.save_bp_file()

    @neovim.command("PUDBToggleAllSigns", sync=False)
    def toggle_signs(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        if not self._toggle_status[buffname]:
            self.sings_on(buffname)
        else:
            self.signs_off(buffname)

    @neovim.command("PUDBOnAllSigns", sync=False)
    def toggle_sign_on(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.buf_initial(buffname)
        self.toggle_sign = True
        self._toggle_status[buffname] = True
        for i in self._bps_placed[buffname]:
            self.nvim.command(
                'sign place {} line={} name={} file={}'.format(
                    i, i // 10, self.sgnname(), buffname))

    @neovim.command("PUDBOffAllSigns", sync=False)
    def toggle_sign_off(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.buf_initial(buffname)
        self.toggle_sign = False
        self._toggle_status[buffname] = False
        for i in self._bps_placed[buffname]:
            self.nvim.command(
                'sign unplace {} file={}'.format(i, buffname))

    def has_breakpoint(self, buffname, lineno):
        if buffname in self._bps_placed and \
                signid(buffname, lineno) in self._bps_placed[buffname]:
            return True
        return False

    def update_pudb_breakpoints(self, buffname):
        bps = []
        if buffname in self._bps_placed:
            for ln in self._bps_placed[buffname]:
                bps.append(self.pudbbp(buffname, int(ln / 10)))
        for bpt in self.iter_breakpoints():
            if bpt.filename == buffname:
                # we already placed these
                continue
            else:
                # make sure we pass on anything we aren't messing with
                bps.append(bpt)
        pudb.settings.save_breakpoints(
            list(map(lambda x: Breakpoint(x.filename, x.lineno), bps)))

    def update_buffer(self, buffname):
        """update_buffer
        Simply updates the buffer signs from the pudb breakpoints, if any
        :param buffname:
        :param toggle_ln:
        """
        if self.toggle_sign:
            for i in self._bps_placed[buffname]:
                self.nvim.command(
                    'sign unplace {} file={}'.format(i, buffname))
            for i in self._bps_placed[buffname]:
                self.nvim.command(
                    'sign place {} line={} name={} file={}'.format(
                        i, i // 10, self.sgnname(), buffname))

    @neovim.command("PUDBLaunchDebuggerTab", sync=True)
    def launchdebugtab(self):
        # if necessary, get the virtual env setup
        # autocmd FileType python nnoremap <silent> <leader>td :tabnew
        # term://source ${HOME}/.virtualenvs/$(cat .dbve)/bin/activate
        # && python -mpudb %<CR>:startinsert<CR>
        new_term_tab_cmd = 'tabnew term://{} -m pudb.run {}'.format(
            self.launcher(),
            self.entrypoint())
        self.nvim.command(new_term_tab_cmd)
        # we have to wait for the terminal to be opened...
        self.nvim.command('startinsert')

    @neovim.command("PUDBStatus", sync=False)
    def pudb_status(self):
        """pudb_status
        print the status of this plugin to :messages in neovim"""
        for key in self._bps_placed:
            self._status_info[key] = [[x // 10 for x in self._bps_placed[key]],
                                      self._toggle_status[key]]
        status_echo_cmd = 'echo "{}\n{}"'.format(
            pprint.pformat(self._status_info),
            pprint.pformat([type(self), self.hlgroup(), self.nvim]))
        self.nvim.command(status_echo_cmd)

    @neovim.command("PUDBToggleBreakPoint", sync=False)
    def toggle_breakpoint_cmd(self, buffname=None):
        """toggle_breakpoint_cmd
        toggles a sign&mark from off to on or none to one
        :param buffname:
        """
        if not buffname:
            buffname = self.cbname()
        row = self.nvim.current.window.cursor[0]
        if self.has_breakpoint(buffname, row):
            self.remove_sign(buffname, row)
        else:
            self.place_sign(buffname, row)
        self.update_pudb_breakpoints(buffname)

    @neovim.command("PUDBSetEntrypoint", sync=False)
    def set_curbuff_as_entrypoint(self, buffname=None):
        '''set_curbuff_as_entrypoint

        Set up the launcher to use the current buffer as the debug entry point.

        :param buffname: override current buffer name
        '''
        if not buffname:
            buffname = self.cbname()
        self.set_entrypoint(buffname)

    @neovim.command("PUDBUpdateBreakPoints", sync=False)
    def update_breakpoints_cmd(self, buffname=None):
        '''update_breakpoints_cmd
        expose the UpdateBreakPoints command
        :param buffname:
        '''
        if not buffname:
            buffname = self.cbname()
        # remove existing signs if any
        self.update_buffer(buffname)

    # set sync so that the current buffer can't change until we are done
    @neovim.autocmd('BufRead', pattern='*.py', sync=True)
    def on_bufread(self, buffname=None):
        '''on_bufread
        expose the BufReadPost autocommand
        :param buffname:
        '''
        if not buffname:
            buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.buf_initial(buffname)
        self.nvim.command(':sign define {} text={} texthl={}'.format(
            self.sgnname(), self.bpsymbol(), self.hlgroup()))
        self.update_buffer(buffname)

    # set sync so that the current buffer can't change until we are done
    @neovim.autocmd('BufNewFile', pattern='*.py', sync=True)
    def on_bufnewfile(self, buffname=None):
        '''on_bufnewfile
        expose the BufNewFile autocommand
        :param buffname:
        '''
        if not buffname:
            buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.buf_initial(buffname)
        self.nvim.command(':sign define {} text={} texthl={}'.format(
            self.sgnname(), self.bpsymbol(), self.hlgroup()))
        self.update_buffer(buffname)

    @neovim.autocmd('BufEnter', pattern='*.py', sync=True)
    def on_buf_enter(self, buffname=None):
        '''on_buf_enter
        expose the BufEnter autocommand
        :param buffname:
        '''
        if not buffname:
            buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.buf_initial(buffname)
        if self._toggle_status[buffname]:
            self.toggle_sign_on()
        else:
            self.toggle_sign_off()

    @neovim.autocmd('TextChanged', pattern='*.py', sync=True)
    def on_text_change(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.buf_initial(buffname)
        self.update_breakpoints_cmd(buffname)

    @neovim.autocmd('InsertLeave', pattern='*.py', sync=True)
    def on_insert_leave(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.buf_initial(buffname)
        self.update_breakpoints_cmd(buffname)
