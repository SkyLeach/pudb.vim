'''
Python3 module for neovim to integrate with the most excellent pudb python
debugger in order to make neovim not only an excellent editor but also a
full-function python IDE.
'''
from bdb import Breakpoint
import sys
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
        self.nvim.command(":sign define {} text={} texthl={}".format(
                self.sgnname(), self.bpsymbol(), self.hlgroup()))
        self._toggle_status = {}
        self._bps_placed = {}  # type: Dict[str,List]
        self._cond_dict = {}  # type: Dict[str,List]
        self._bp_config_dir = ""
        self._bp_file = ""
        launcher_version_command = ' -c "import sys;print(sys.version_info[:2])"'
        self._launcher_version = list(map(int, os.popen(
                self.launcher() +
                launcher_version_command).read().strip()[1:-1].split(',')))
        self.load_base_dir()
        self.load_bp_file()
        # update the __logger__ to use neovim for messages
        nvimhandler = NvimOutLogHandler(nvim)
        # nvimhandler.setLevel(logging.INFO)
        nvimhandler.setLevel(logging.DEBUG)
        __logger__.setLevel(logging.DEBUG)
        __logger__.addHandler(nvimhandler)
        # define our sign command

    @neovim.command("PUDBClearAllBreakpoints", sync=True)
    def clear_all_bps(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.test_buffer(buffname)
        for num_line in self._toggle_status[buffname][:]:
            self.remove_sign(buffname, num_line)
        self._bps_placed[buffname] = []
        self.save_bp_file()

    @neovim.command("PUDBRemoveBreakpoints", sync=True)
    def remove_bp_file(self):
        os.remove(self._bp_file)
        self.blank_file()
        self.load_bp_file()
        self.update_sign()

    @neovim.command("PUDBOnAllSigns", sync=True)
    def signs_on(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.test_buffer(buffname)
        for num_line in self._bps_placed[buffname]:
            self.place_sign(buffname, num_line)

    @neovim.command("PUDBOffAllSigns", sync=True)
    def signs_off(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.test_buffer(buffname)
        tmp = self._toggle_status[buffname][:]
        for num_line in tmp:
            self.remove_sign(buffname, num_line)

    @neovim.command("PUDBLaunchDebuggerTab", sync=True)
    def launchdebugtab(self):
        new_term_tab_cmd = 'tabnew term://{} -m pudb.run {}'.format(
                self.launcher(), self.entrypoint())
        self.nvim.command(new_term_tab_cmd)
        self.nvim.command('startinsert')

    @neovim.command("PUDBStatus", sync=True)
    def pudb_status(self):
        status_info = {}
        for buffname in self._bps_placed:
            status_info[buffname] = [self._bps_placed[buffname],
                                     bool(self._toggle_status[buffname])]
        self.print_feature(status_info)

    @neovim.command("PUDBToggleBreakPoint", sync=True)
    def toggle_bp(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        num_line = self.nvim.current.window.cursor[0]
        self.load_bp_file()

        if num_line not in self._bps_placed[buffname]:
            self._bps_placed[buffname].append(num_line)
            self._bps_placed[buffname].sort()
        else:
            self._bps_placed[buffname].remove(num_line)
        if num_line in self._toggle_status[buffname]:
            self.remove_sign(buffname, num_line)
        else:
            self.place_sign(buffname, num_line)
        self.save_bp_file()

    @neovim.command("PUDBSetEntrypoint", sync=True)
    def set_curbuff_as_entrypoint(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        self.set_entrypoint(buffname)

    @neovim.command("PUDBUpdateBreakPoints", sync=True)
    def update_sign(self, buffname=None):
        if not buffname:
            buffname = self.cbname()
        tmp = self._toggle_status[buffname]
        if tmp:
            self.signs_off(buffname)
            self.signs_on(buffname)
        # self.print_feature([self._toggle_status, self._bps_placed,
        #                     self.debugger, buffname])

    @neovim.autocmd('TextChanged', pattern='*.py', sync=True)
    def on_txt_changed(self):
        buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.update_sign(buffname)

    @neovim.autocmd('BufEnter', pattern='*.py', sync=True)
    def on_buf_enter(self):
        buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.load_bp_file()
        self.update_sign(buffname)

    @neovim.autocmd('TermLeave', pattern='*.py', sync=True)
    def on_term_close(self):
        buffname = self.cbname()
        if buffname[:7] == 'term://':
            return
        self.load_bp_file()
        self.update_sign(buffname)

    def test_buffer(self, buffname):
        if buffname not in self._bps_placed:
            self._bps_placed[buffname] = []
        if buffname not in self._toggle_status:
            self._toggle_status[buffname] = []

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
            self.test_buffer(buffname)
            self._bps_placed[buffname].append(int(num_line[0]))

        for buffname in self._bps_placed:
            self._bps_placed[buffname] = list(set(self._bps_placed[buffname]))
            self._bps_placed[buffname].sort()

        buffname = self.cbname()
        self.test_buffer(buffname)

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
        tmp_path = '{}saved-breakpoints-{}.{}'.format(
                self._bp_config_dir, *self._launcher_version)
        if not os.path.exists(tmp_path):
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
        return sorted((files))

    def place_sign(self, buffname, num_line):
        signcmd = "sign place {} line={} name={} file={}".format(
            num_line * 10, num_line, self.sgnname(), buffname)
        self.nvim.command(signcmd)
        if num_line not in self._toggle_status[buffname]:
            self._toggle_status[buffname].append(num_line)
        self._toggle_status[buffname].sort()

    def remove_sign(self, buffname, num_line):
        signcmd = 'sign unplace {} file={}'.format(num_line * 10, buffname)
        self.nvim.command(signcmd)
        if num_line in self._toggle_status[buffname]:
            self._toggle_status[buffname].remove(num_line)

    def has_breakpoint(self, buffname, num_line):
        self.test_buffer(buffname)
        if num_line in self._bps_placed[buffname]:
            return True
        return False

    def print_feature(self, print_input):
        print_feature = 'echo "{}"'.format(pprint.pformat(print_input))
        self.nvim.command(print_feature)
