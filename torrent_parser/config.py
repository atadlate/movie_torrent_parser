__author__ = 'mcharbit'

import os
import sys
import pickle
import unicodedata
import getpass
import copy
import re
import logging
import platform
from crontab import CronTab

status = "init"
config = dict()
default_log_file = os.path.join(os.path.dirname(sys.argv[0]), "parser_log.txt")
file_log = ""

def prompt_hidden(prompt):
    return getpass.getpass(prompt).strip()

def prompt(prompt):
    return raw_input(prompt).strip()

def encrypt_pass(password=""):

    encrypted_pass = u""
    for index in range(len(password)):
        char = password[index]
        encrypted_char = unichr((index+1) * ord(char) - (len(password) - (index)))
        encrypted_pass += encrypted_char

    return encrypted_pass

def decrypt_pass(password=""):

    decrypted_pass = ""
    for index in range(len(password)):
        byte = password[index]
        decrypted_char = chr((ord(byte) + (len(password) - (index)))/(index+1))
        decrypted_pass += decrypted_char

    return decrypted_pass

def set_cron(mode, file_config):

    if mode in ['daily', 'startup', 'weekly']:

        my_name = sys.argv[0]
        script_dir = os.path.abspath(os.path.join(os.path.dirname(my_name), 'scripts'))
        auto_run_config_file = os.path.join(script_dir, 'auto_run_config.txt')
        script_name = os.path.join(script_dir, 'auto_run.py')

        auto_run_config = dict()
        auto_run_config['file_config'] = os.path.abspath(file_config)

        vname = prompt("Name of the virtual_env to activate before the script is run (leave blank if standard python interpreter): ")
        if vname != "":

            venv_path = prompt("Path to virtual env's location (leave blank if in WORKON_HOME): ")
            if venv_path == "":
                vpath = os.path.join(os.environ['WORKON_HOME'], vname)
            else:
                vpath = os.path.abspath(os.path.join(venv_path, vname))

            if os.name == 'posix':
                vpython = os.path.join(vpath, 'bin', 'python')
            else:
                vpython = os.path.join(vpath, 'Scripts', 'python.exe')

            if os.path.exists(vpython):
                auto_run_config['virtual_env'] = vpython
            else:
                log_message('Interpreter {} couldn\'t be found. Auto-run not set'.format(vpython), 'error')
                return

        autorun_log_file = prompt("Path to the log file to use for automatic run: ")
        if autorun_log_file != "":
            auto_run_config['log_file'] = os.path.abspath(autorun_log_file)

        auto_run_config['mode'] = mode

        with open(auto_run_config_file, 'wb') as fd:
            pickle.dump(auto_run_config, fd)

        if os.name == 'posix':
            # Delay a bit program start to be sure all services are on
            cmd = 'sleep 30 && python ' + script_name + "\n"

            # Erase any previous job related to torrent-parser auto-run
            # torrents_jobs = user_cron.find_command(cmd)
            user_cron = CronTab(user=True)
            for user_job in user_cron.crons[:]:
                if re.search(r'torrent_parser.*auto_run\.py', user_job.command):
                    user_cron.remove(user_job)

            # Schedule a new job that will execute at every system reboot and check the last execution date
            job = user_cron.new(command=cmd, comment='auto-run of movie-torrent-parser')
            job.every_reboot()
            job.enable()
            user_cron.write()

        elif os.name == 'nt':
            cmd = 'python ' + script_name

            if os.environ.has_key('USERNAME'):
                try:
                    is_xp = (platform.win32_ver()[0] == 'XP')
                except:
                    is_xp = False
                if is_xp:
                    startup_folder = "C:\\Documents and Settings\\" + os.environ.get('USERNAME') + \
                                     "\\Start Menu\\Programs\\Startup"
                else:
                    startup_folder = "C:\\Users\\" + os.environ.get('USERNAME') + \
                                     "\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"

                movie_batch = startup_folder + "\\movie_torrent.cmd"
                with open(movie_batch, 'w') as fd:
                    fd.write(cmd)


def get_config_from_user():
    global config

    print " => Please enter your preferences\n"

    method = prompt('Would you like the report to be displayed on the console or sent by mail? (console/mail):')
    if method.lower() == "mail" or method.lower() == "m":
        config['method'] = 'mail'
    else:
        config['method'] = 'console'

    if config['method'] == 'mail':
        config['from'] = prompt('Mail sent from: ')
        config['to'] = prompt('Mail sent to: ')
        config['smtp_server'] = prompt('SMTP server: ')
        config['username'] = prompt('Username: ')
        config['password'] = prompt_hidden('Password: ')
        mail_format = prompt('Mail format (text/html):')
        if mail_format.lower() == 'h' or mail_format.lower() == 'html':
            config['mail_format'] = 'html'
        else:
            config['mail_format'] = 'text'

    save = prompt('Would you like to save config to a file ? (Y/N): ')
    if save.lower() == "yes" or save.lower() == "y":

        config_path = prompt('  File path (case sensitive): ')

        try:
            with open(config_path, 'wb') as fd:
                saved_config = copy.deepcopy(config)
                if config['method'] == 'mail':
                    saved_config['password'] = encrypt_pass(config['password'])

                pickle.dump(saved_config, fd)
        except:
            log_message("An exception occured. Config not saved to file", 'error')
        else:

            if os.name in ['posix', 'nt']:
                auto_type_cfm = prompt(
                    "Would you like to start the script automatically with this configuration ?\n" +
                    "This will replace previous settings for automatic start if any.\n" +
                    "(Y/N): ")

                if auto_type_cfm.lower() in ['yes', 'y']:
                    auto_type = prompt(
                        "How often would you like the auto-run to execute ?\n" +
                        "- At every system startup (S)\n" +
                        "- Daily (D)\n" +
                        "- Weekly (W): ")

                    if auto_type.lower() in ["startup", "s"]:
                        set_cron('startup', config_path)
                    elif auto_type.lower() in ["daily", "d"]:
                        set_cron('daily', config_path)
                    elif auto_type.lower() in ["weekly", "w"]:
                        set_cron('weekly', config_path)
                    else:
                        log_message(auto_type + ' is not a valid choice. Auto-run not set.', 'error')

    console_log("\n")

def get_config():
    global config
    global status
    global default_log_file
    global file_log

    file_config = None
    file_log = None
    log_to_file = False
    background_mode = False

    usage = "Usage: python parser.py [ name_of_your_config_file ] [ -b ] [ -l log_file ]"

    if len(sys.argv) > 1:
        # Retrieve arguments that were passed to the script
        waiting_for_log = False
        for index in range(1, len(sys.argv)):
            argument = sys.argv[index]
            if argument == '-l':
                waiting_for_log = True
                log_to_file = True
            elif argument == '-b':
                background_mode = True
            else:
                if waiting_for_log:
                    file_log = argument
                    waiting_for_log = False
                else:
                    if file_config is None:
                        file_config = argument
                    else:
                        print "Invalid argument passed to script"
                        print usage
                        # Exiting
                        status = 'crash'
                        sys.exit()

    # Determining logging method
    if log_to_file:
        if file_log is None:
            file_log = default_log_file
        try:
            logging.basicConfig(filename=file_log, filemode='w', level=logging.INFO,
                                format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        except:
            log_to_file=False

    if not log_to_file:
        file_log = ""
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    if file_config is not None:
        if os.path.exists(file_config):
            try:
                with open(file_config, 'rb') as fd:
                    config = pickle.load(fd)
            except:
                log_message("Couldn't open config file " + file_config, 'error')
        else:
            log_message(file_config + " is not a valid path", 'error')

    if config.has_key('password'):
        config['password'] = decrypt_pass(config['password'])

    if config.has_key('method'):

        if config['method'] == 'mail':

            if not (config.has_key('username')
                and config.has_key('smtp_server')
                and config.has_key('password')
                and config.has_key('from')
                and config.has_key('to')
                and config.has_key('mail_format')):
                    if background_mode:
                        log_message("Invalid configuration while in background mode", 'error')
                        status = 'crash'
                        sys.exit()
                    else:
                        get_config_from_user()

    else:
        if background_mode:
            log_message("Invalid configuration while in background mode", 'error')
            status = 'crash'
            sys.exit()
        else:
            get_config_from_user()

    status = 'ok'

def console_log(text_content):

    global file_log

    if not isinstance(text_content, unicode):
        text_content = unicode(text_content, 'utf-8')

    if file_log == "":
        try:
            print text_content.strip().encode('utf-8')
        except UnicodeEncodeError:
            ascii_text_content = unicodedata.normalize('NFKD', text_content).encode('ascii', 'ignore')
            print ascii_text_content.strip()
    else:
        with open(file_log, 'a') as fd:
            fd.write(text_content.strip().encode('utf-8'))

def log_message(text_content, type='info'):

    if type == 'error':
        logger = logging.error
    else:
        logger = logging.info

    if not isinstance(text_content, unicode):
        text_content = unicode(text_content, 'utf-8')

    logger(text_content.strip().encode('utf-8'))
