__author__ = 'mcharbit'

import pickle
import os
import sys
import subprocess
import urllib2
from time import sleep

auto_run_config_file_name = "auto_run_config.txt"
auto_run_config = os.path.join(os.path.dirname(sys.argv[0]), auto_run_config_file_name)

script_file = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), os.path.pardir, 'parser.py'))
default_script_log = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), os.path.pardir, 'parser_log.txt'))
default_vhome = os.path.join(os.environ['HOME'], '.virtualenvs')
run_config = dict()

def internet_on():
    try:
        response=urllib2.urlopen('http://www.google.com',timeout=1)
        return True
    except urllib2.URLError as err: pass
    return False

def exit():
    print "*** Problem during auto-run ***\n"
    print "Exiting\n"
    sys.exit()

if os.path.exists(auto_run_config):
    try:
        with open(auto_run_config, 'rb') as fd:
            run_config = pickle.load(fd)
    except:
        exit()

    python_bin = 'python'

    if run_config.has_key('virtual_env'):
        vname = run_config['virtual_env']

        if os.environ.has_key('WORKON_HOME'):
            vpath = os.path.join(os.environ['WORKON_HOME'], vname)
        else:
            vpath = os.path.join(default_vhome, vname)

        vpython = os.path.join(vpath, 'bin', 'python')

        if os.path.exists(vpython):
            python_bin = vpython

    if run_config.has_key('log_file'):
        script_log = os.path.abspath(run_config['log_file'])
    else:
        script_log = default_script_log

    if run_config.has_key('file_config'):
        config_file = run_config['file_config']

        if os.path.exists(config_file) and os.path.exists(script_file):
            network_ok = False
            for i in range(10):
                network_ok = internet_on()
                if network_ok:
                    break
                else:
                    sleep(3)
            if network_ok:
                subprocess.call([python_bin, script_file, config_file, '-l', script_log, '-b'])
            else:
                exit()
        else:
            exit()
    else:
        exit()

else:
    exit()