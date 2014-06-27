__author__ = 'mcharbit'

import pickle
import os
import sys
import subprocess
import urllib2
import logging
from time import sleep, time
from datetime import date

auto_run_config_file_name = "auto_run_config.txt"
auto_run_config = os.path.join(os.path.dirname(sys.argv[0]), auto_run_config_file_name)
last_auto_run_execution = "last_auto_run_execution.txt"
last_auto_run_execution = os.path.join(os.path.dirname(sys.argv[0]), last_auto_run_execution)

script_file = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), os.path.pardir, 'parser.py'))
default_script_log = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), os.path.pardir, 'parser_log.txt'))
run_config = dict()

def internet_on():
    try:
        response=urllib2.urlopen('http://www.google.com',timeout=1)
        return True
    except urllib2.URLError as err: pass
    return False

def main():
    if os.path.exists(auto_run_config):
        try:
            with open(auto_run_config, 'rb') as fd:
                run_config = pickle.load(fd)
        except:
            logging.error("problem while opening {}".format(auto_run_config))
            sys.exit()

        execute_script = False
        if run_config.has_key('mode') and run_config['mode'] in ['daily', 'weekly']:
            if os.path.exists(last_auto_run_execution):
                with open(last_auto_run_execution, 'r') as fd:
                    try:
                        last_execution = date.fromtimestamp(float(fd.read()))
                    except:
                        # Assume not executed before
                        execute_script = True
                    else:
                        today = date.today()
                        difference = (today - last_execution).days
                        if (difference >= 7 and run_config['mode'] == 'weekly') \
                                or (difference >= 1 and run_config['mode'] == 'daily'):
                            execute_script = True
            else:
                # Assume not executed before
                execute_script = True
        else:
            # Assume at every system_startup. Continue execution
            execute_script = True

        if execute_script:
            python_bin = 'python'

            if run_config.has_key('virtual_env'):
                vpython = run_config['virtual_env']

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
                        with open(last_auto_run_execution, 'w') as fd:
                            fd.write(str(time()))
                    else:
                        logging.error("Network not available after max number of attempts")
                        sys.exit()
                else:
                    logging.error("{} or {} are missing".format(config_file, script_file))
                    sys.exit()
            else:
                logging.error("{} has an invalid format".format(auto_run_config))
                sys.exit()
        else:
            sys.exit()
    else:
        logging.error("{} is not a valid path".format(auto_run_config))
        sys.exit()

if __name__ == "__main__":
    main()
