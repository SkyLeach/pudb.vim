#!/usr/bin/env python
# vim: ts=4 sw=4 sts=4 et

# global
import os
import sys
import unittest
import logging
import neovim
# module-level logger
logger = logging.getLogger(__name__)

# module-global test-specific imports
# where to put test output data for compare.
testdatadir = os.path.join(
    os.path.dirname(__file__), '..', 'rplugin', 'python3')
# add the plugin to the path for import
sys.path.append(os.path.abspath(testdatadir))
import vim_pudb
purge_results = False


class TestPUDBPlugin(unittest.TestCase):
    '''
        TestPUDBPlugin
    '''
    testdatadir = None

    def __init__(self, *args, **kwargs):
        self.testdatadir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), testdatadir)
        super(TestPUDBPlugin, self).__init__(*args, **kwargs)
        # check for kwargs
        # this allows test control by instance
        self.testdatadir = kwargs.get('testdatadir', testdatadir)

    def setUp(self):
        '''setUp
        pre-test setup called before each test
        '''
        logging.debug('setUp')
        if not os.path.exists(self.testdatadir):
            os.mkdir(self.testdatadir)
        else:
            self.assertTrue(os.path.isdir(self.testdatadir))
        self.assertTrue(os.path.exists(self.testdatadir))

    def tearDown(self):
        '''tearDown
        post-test cleanup, if required
        '''
        logging.debug('tearDown')

    def test_something_0(self):
        '''test_something_0
            auto-run tests sorted by ascending alpha
        '''
        pass

    def default_test(self):
        '''testFileDetection
        Tests all data files for type and compares the results to the current
        stored results.
        '''
        # try embedding nvim in order to run the tests
        # os.environ['NVIM_LISTEN_ADDRESS']=
        # nvim = neovim.attach('child',
        #     argv=["/usr/bin/env", "nvim", "--embed"])
        nvim = neovim.attach('socket', path='/var/folders/kt/yxsj572j6z18h6gq073_zvdr0000gn/T/nvim1jLDkU/0')
        myplug = vim_pudb.NvimPudb(nvim)
        tv = myplug.sgnname()
        self.assertIsNotNone(tv)
        myplug.set_sgnname('bogus')
        self.assertEquals(myplug.sgnname(), 'bogus')
        myplug.set_sgnname(tv)
        tv = myplug.bpsymbol()
        self.assertIsNotNone(tv)
        myplug.set_bpsymbol('bogus')
        self.assertEquals(myplug.bpsymbol(), 'bogus')
        myplug.set_bpsymbol(tv)
        tv = myplug.hlgroup()
        self.assertIsNotNone(tv)
        myplug.set_lgroup('bogus')
        self.assertEquals(myplug.hlgroup(), 'bogus')
        myplug.set_lgroup(tv)
        tv = myplug.launcher()
        self.assertIsNotNone(tv)
        myplug.set_launcher('bogus')
        self.assertEquals(myplug.launcher(), 'bogus')
        myplug.set_launcher(tv)
        tv = myplug.nvim_python()
        self.assertIsNotNone(tv)
        tv = myplug.nvim_python3()
        self.assertIsNotNone(tv)
        tv = myplug.entrypoint()
        self.assertIsNotNone(tv)
        myplug.set_entrypoint('bogus')
        self.assertEquals(myplug.entrypoint(), 'bogus')
        myplug.set_entrypoint(tv)
        tv = myplug.cbname()
        self.assertIsNotNone(tv)
        # test setting the venv
        myplug.set_curbuff_as_entrypoint_with_venv(
            buffname='/Users/magregor/src/pudb.vim/test/test_plugin.py')


# stand-alone test execution
if __name__ == '__main__':
    import nose2
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    nose2.main(
        argv=[
            'fake',
            '--log-capture',
            'TestPUDBPlugin.default_test',
        ])
