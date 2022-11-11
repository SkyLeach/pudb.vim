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
    def sings_on(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self._toggle_status[buffname] = True
        self.test_buffer(buffname)
        for num_line in self._bps_placed[buffname]:
            self.place_sign(buffname, num_line)

    @neovim.command("PUDBOffAllSigns", sync=False)
    def signs_off(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self._toggle_status[buffname] = False
        self.test_buffer(buffname)
        for num_line in self._bps_placed[buffname]:
            self.remove_sign(buffname, num_line)

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

    def test_buffer(self, buffname):
        if buffname not in self._bps_placed:
            self._bps_placed[buffname] = []
        if buffname not in self._toggle_status:
            self._toggle_status[buffname] = False

    def load_bp_file(self):
        self.make_links()
        self._bps_placed = {}
        self._cond_dict = {}

        lines = []
        with open(self._bp_file, "r") as f:
            lines.extend([line.strip() for line in f.readlines()])

        for line in lines:
            buffname, num_line = line[2:].split(':')
            num_line = num_line.split(', ')

            if len(num_line) > 1:
                self._cond_dict["{}:{}".format(
                        buffname, num_line[0])] = ", ".join(num_line[1:])

            if buffname in self._bps_placed:
                self._bps_placed[buffname].append(int(num_line[0]))
            else:
                self._bps_placed[buffname] = [int(num_line[0])]
            self._bps_placed[buffname] = list(set(self._bps_placed[buffname]))
            self._bps_placed[buffname].sort()

            if buffname not in self._toggle_status:
                self._toggle_status[buffname] = False

        self.test_buffer(self.cbname())

    def save_bp_file(self):
        self.make_links()
        with open(self._bp_file, "w") as f:
            for buffname in sorted(self._bps_placed):
                self._bps_placed[buffname] = list(set(self._bps_placed[buffname]))
                self._bps_placed[buffname].sort()
                for num_line in self._bps_placed[buffname]:
                    cond_line = "{}:{}".format(buffname, num_line)
                    if cond_line in self._cond_dict:
                        f.write('b {}:{}, {}\n'.format(buffname,
                                                       num_line,
                                                       self._cond_dict[cond_line]))
                    else:
                        f.write('b {}:{}\n'.format(buffname, num_line))

    def blank_file(self):
        if not os.path.exists(self._bp_file):
            with open(self._bp_file, "w") as f:
                pass

    def make_links(self):
        self.blank_file()
        for bp_file in self.find_bp_files():
            tmp_path = self._bp_config_dir + bp_file
            if not os.path.islink(tmp_path):
                with open(tmp_path, "r") as f:
                    tmp_input = f.read()
                with open(self._bp_file, "a") as f:
                    f.write(tmp_input)
                os.remove(tmp_path)
                os.symlink(self._bp_file, tmp_path)

    def load_base_dir(self):
        _home = os.environ.get("HOME", os.path.expanduser("~"))
        xdg_config_home = os.environ.get(
            "XDG_CONFIG_HOME",
            os.path.join(_home, ".config") if _home else None)

        if xdg_config_home:
            xdg_config_dirs = [xdg_config_home]
        else:
            xdg_config_dirs = os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":")
        self._bp_config_dir = xdg_config_dirs[0] + "/pudb/"
        self._bp_file = xdg_config_dirs[0] + "/pudb/saved-breakpoints"

    def find_bp_files(self):
        files = []
        breakpoints_file_name = "saved-breakpoints-"
        for entry in os.listdir(self._bp_config_dir):
            if breakpoints_file_name in entry:
                files.append(entry)
        return sorted(list(set(files)))

    def place_sign(self, buffname, lineno):
        signcmd = "sign place {} line={} name={} file={}".format(
            lineno * 10, lineno, self.sgnname(), buffname)
        self.nvim.command(signcmd)

    def remove_sign(self, buffname, lineno):
        signcmd = 'sign unplace {} file={}'.format(
            lineno, buffname)
        self.nvim.command(signcmd)

    def has_breakpoint(self, buffname, lineno):
        self.test_buffer(buffname)
        if lineno in self._bps_placed[buffname]:
            return True
        return False

    def print_feature(self, print_input):
        print_feature = 'echo "{}"'.format(pprint.pformat(print_input))
        self.nvim.command(print_feature)

