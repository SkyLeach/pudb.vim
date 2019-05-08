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
        self.nvim.command("let g:pudb_entry_point='{}'".format(entrypoint))

    # @property
    def pudb_signify(self):
        return self.nvim.vars.get('pudb_signify', 0)

    # @entrypoint.setter
    def set_pudb_signify(self, pudb_signify):
        self.nvim.command("let g:pudb_signify='{}'".format(pudb_signify))

    # @property
    def cbname(self):
        """cbname
        returns the current buffer's name attribute
        """
        return self.nvim.current.buffer.name

    def __init__(self, nvim=None):
        # set our nvim hook first...
        self.nvim = nvim
        self._toggle_status = dict()
        self._status_info = dict()
        self._bps_placed = dict()  # type: Dict[str,List]
        self.pudbbp = collections.namedtuple('Breakpoint',
                                             ['filename', 'lineno'])
        self.toggle_sign = False
        # update the __logger__ to use neovim for messages
        nvimhandler = NvimOutLogHandler(nvim)
        # nvimhandler.setLevel(logging.INFO)
        nvimhandler.setLevel(logging.DEBUG)
        __logger__.setLevel(logging.DEBUG)
        __logger__.addHandler(nvimhandler)
        # define our sign command
        # super().__init__()

    def iter_breakpoints(self, buffname=None):
        """iter_breakpoints
        iterates over the breakpoints registered with pudb for this buffer
        """
        for brpt in pudb.settings.load_breakpoints():
            if not buffname:
                yield self.pudbbp(*brpt[:2])
            elif buffname == brpt[0]:
                yield self.pudbbp(*brpt[:2])

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
        """clear_all_bps
        removes all signs from the buffer and all breakpoints from pudb
        :param buffname:
        """
        if not buffname:
            buffname = self.cbname()
        if buffname in self._bps_placed:
            for i in self._bps_placed[buffname]:
                self.nvim.command('sign unplace {} file={}'.format(i,
                                                                   buffname))
        self._bps_placed[buffname] = []
        self.update_pudb_breakpoints(buffname)

    @neovim.command("PUDBToggleAllSigns", sync=False)
    def toggle_all_signs(self, buffname=None):
        """toggle_all_signs
        removes all signs from the buffer
        :param buffname:
        """
        if not buffname:
            buffname = self.cbname()
        if not self.toggle_sign:
            self.toggle_sign = True
            if self.pudb_signify():
                self.nvim.command('SignifyDisable')
            for key in self._bps_placed:
                for i in self._bps_placed[key]:
                    self.nvim.command(
                        'sign place {} line={} name={} file={}'.format(
                            i, i // 10, self.sgnname(), buffname))
        else:
            self.toggle_sign = False
            for key in self._bps_placed:
                for i in self._bps_placed[key]:
                    self.nvim.command(
                        'sign unplace {} file={}'.format(i, buffname))
            if self.pudb_signify():
                self.nvim.command('SignifyEnable')

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
            for key in self._bps_placed:
                for i in self._bps_placed[key]:
                    self.nvim.command(
                        'sign unplace {} file={}'.format(i, buffname))
                for i in self._bps_placed[key]:
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
            self._status_info[key] = [x // 10 for x in self._bps_placed[key]]
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

    def get_buffer_venv_launcher(self, buffname=None):
        if not buffname:
            buffname = self.cbname()

        def getpath(project):
            try:
                with open(os.path.join(project, '.project')) as pfile:
                    return pfile.readline().strip()
            except Exception:
                # probably no .project file
                return '.'

        def projectiter(ppaths):
            for project in ppaths:
                yield getpath(project)

        for root, dirs, files in os.walk(os.path.expanduser(
                '~/.virtualenvs')):
            venvs = set(dirs).difference(('bin', 'lib', 'include'))
            # venvs = list(map(lambda x: os.path.join(root,x), venvs))
            for ppath in projectiter(
                    map(lambda x: os.path.join(root, x), venvs)):
                if buffname.startswith(os.path.join(root, ppath)):
                    return os.path.join(os.path.join(
                        root, ppath), 'bin', 'python')
        return self.launcher()

    @neovim.command("PUDBSetEntrypointVENV", sync=False)
    def set_curbuff_as_entrypoint_with_venv(self, buffname=None):
        '''set_curbuff_as_entrypoint_with_venv

        :param buffname: override the current buffer
        '''
        self.set_curbuff_as_entrypoint(buffname=buffname, set_venv=True)

    @neovim.command("PUDBSetEntrypoint", sync=False)
    def set_curbuff_as_entrypoint(self, buffname=None, set_venv=False):
        '''set_curbuff_as_entrypoint

        Set up the launcher to use the current buffer as the debug entry point.
        By default this will not use the buffer's virtualenv.  Use
        PUDBSetEntrypointVENV for that.

        :param buffname: override current buffer name
        :param set_venv: attempt to find and set the buffer's relative virtual
        environment from ~/.virtualenvs/<venvs>/.project
        '''
        if not buffname:
            buffname = self.cbname()
        if set_venv:
            self.set_launcher(self.get_buffer_venv_launcher(buffname))
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
        self.nvim.command(':sign define {} text={} texthl={}'.format(
            self.sgnname(), self.bpsymbol(), self.hlgroup()))
        self.update_buffer(buffname)
