__author__ = 'mcharbit'

import os
import sys
import pickle
import unicodedata
import getpass
import copy
from crontab import CronTab

config_ok = False
config = dict()
default_log_file = os.path.join(os.path.dirname(sys.argv[0]), "parser_log.txt")
logger = 'console'

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

    if mode in ['daily', 'startup']:

        my_name = sys.argv[0]
        script_dir = os.path.abspath(os.path.join(os.path.dirname(my_name), 'scripts'))
        auto_run_config_file = os.path.join(script_dir, 'auto_run_config.txt')
        script_name = os.path.join(script_dir, 'auto_run.py')
        cmd = 'python ' + script_name

        auto_run_config = dict()
        auto_run_config['file_config'] = os.path.abspath(file_config)

        venv = prompt("Name of the virtual_env to activate before the script is run (leave blank if standard python interpreter): ")
        if venv != "":
            auto_run_config['virtual_env'] = venv

        with open(auto_run_config_file, 'wb') as fd:
            pickle.dump(auto_run_config, fd)

        user_cron = CronTab(user=True)

        # Erase any previous job related to torrent-parser auto-run
        torrents_jobs = user_cron.find_command(cmd)
        for torrent_job in torrents_jobs:
            user_cron.remove(torrent_job)

        job = user_cron.new(command=cmd, comment='auto-run of movie-torrent-parser')

        if mode == 'daily':
            job.every(1).days()
        elif mode == 'startup':
            job.every_reboot()

        job.enable()
        user_cron.write()

def get_config_from_user():
    global config

    print "Configuration file not passed to script or invalid.\n"
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
            print "   An exception occured. Config not saved to file\n"
        else:
            auto_type = prompt(
                """Would you like to start the script automatically with this configuration ?
(will replace previous settings for automatic start if any)
    - At every system startup
    - Daily
    - Never
(startup/daily/never): """)
            if auto_type.lower() == "startup" or auto_type.lower() == "s":
                set_cron('startup', config_path)
            elif auto_type.lower() == "daily" or auto_type.lower() == "d":
                set_cron('daily', config_path)

    print "\n"

def get_config():
    global config
    global config_ok
    global default_log_file
    global logger

    file_config = None
    file_log = None

    if len(sys.argv) > 1:
        # Retrieve arguments that were passed to the script
        waiting_for_log = False
        for index in range(1, len(sys.argv)):

            argument = sys.argv[index]
            if argument == '-l':
                waiting_for_log = True
            else:
                if waiting_for_log:
                    file_log = argument
                    waiting_for_log = False
                else:
                    file_config = argument

    # Determining logging method
    if file_log is not None:
        if not os.path.exists(file_log):
            file_log = default_log_file
        try:
            logger = open(file_log, 'w')
        except:
            logger = 'console'

    if file_config is not None:
        if os.path.exists(file_config):
            try:
                with open(file_config, 'rb') as fd:
                    config = pickle.load(fd)
            except:
                console_log("*** Error opening config file " + file_config)
        else:
            console_log(file_config + " is not a valid path")

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
                    get_config_from_user()

    else:
        get_config_from_user()

    config_ok = True

def console_log(text_content):

    global logger

    if not isinstance(text_content, unicode):
        text_content = unicode(text_content, 'utf-8')

    if isinstance(logger, file):
        logger.write(text_content.encode('utf-8'))
    else:
        try:
            print text_content.strip().encode('utf-8')
        except UnicodeEncodeError:
            ascii_text_content = unicodedata.normalize('NFKD', text_content).encode('ascii', 'ignore')
            print ascii_text_content.strip()
