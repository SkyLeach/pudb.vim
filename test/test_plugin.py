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
        # nvim = neovim.attach('child', argv=["/usr/bin/env", "nvim", "--embed"])
        nvim = neovim.attach('socket', path='/var/folders/kt/yxsj572j6z18h6gq073_zvdr0000gn/T/nvim5K7tM0/0')
        myplug = vim_pudb.NvimPudb(nvim)
        self.assertIsNotNone(myplug.sgnname)
        self.assertIsNotNone(myplug.bpsymbol)
        self.assertIsNotNone(myplug.hlgroup)
        self.assertIsNotNone(myplug.launcher)
        self.assertIsNotNone(myplug.entrypoint)
        self.assertIsNotNone(myplug.cbname)


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


