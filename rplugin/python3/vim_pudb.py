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

    @neovim.command("PUDBRemoveBreakpoints", sync=False)
    def remove_bp_file(self):
        os.remove(self._bp_file)
        self.blank_file()

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

    @neovim.command("PUDBLaunchDebuggerTab", sync=True)
    def launchdebugtab(self):
        new_term_tab_cmd = 'tabnew term://{} -m pudb.run {}'.format(
                self.launcher(), self.entrypoint())
        self.nvim.command(new_term_tab_cmd)
        self.nvim.command('startinsert')

    @neovim.command("PUDBStatus", sync=False)
    def pudb_status(self):
        status_info = {}
        for buffname in self._bps_placed:
            status_info[buffname] = [
                    [num_line for num_line in self._bps_placed[buffname]],
                    self._toggle_status[buffname]]
        self.print_feature(status_info)

    @neovim.command("PUDBToggleBreakPoint", sync=False)
    def toggle_bp(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        num_line = self.nvim.current.window.cursor[0]

        if num_line not in self._bps_placed[buffname]:
            self._bps_placed[buffname].append(num_line)
            self._bps_placed[buffname].sort()
        else:
            self._bps_placed[buffname].remove(num_line)
        self.update_sign(buffname)
        self.save_bp_file()

    @neovim.command("PUDBSetEntrypoint", sync=False)
    def set_curbuff_as_entrypoint(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.set_entrypoint(buffname)

    @neovim.command("PUDBUpdateBreakPoints", sync=False)
    def update_sign(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        if self._toggle_status[buffname]:
            self.signs_off(buffname)
            self.sings_on(buffname)

    # set sync so that the current buffer can't change until we are done
    @neovim.autocmd('BufRead', pattern='*.py', sync=True)
    def on_bufread(self):
        self.update_buffer()

    # set sync so that the current buffer can't change until we are done
    @neovim.autocmd('BufNewFile', pattern='*.py', sync=True)
    def on_bufnewfile(self):
        self.update_buffer()

    @neovim.autocmd('BufEnter', pattern='*.py', sync=True)
    def on_buf_enter(self):
        self.update_buffer()

    @neovim.autocmd('TextChanged', pattern='*.py', sync=True)
    def on_text_change(self):
        self.update_buffer()

    @neovim.autocmd('InsertLeave', pattern='*.py', sync=True)
    def on_insert_leave(self):
        self.update_buffer()

    def update_buffer(self):
        buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.nvim.command(":sign define {} text={} texthl={}".format(
                self.sgnname(), self.bpsymbol(), self.hlgroup()))
        self.load_bp_file()
        if self._toggle_status[buffname]:
            self.update_sign()

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

