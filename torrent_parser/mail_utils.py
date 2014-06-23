__author__ = 'mcharbit'

import os
import sys
import smtplib
import pickle
import unicodedata

from email.mime.text import MIMEText
from time import sleep

script_executed = False
config_ok = False
server_connected = False
server = None
config = dict()

def format_report(list_movie, list_movie_discarded):

    html_content = text_content = unicode()

    html_content += """\
    <html>
      <head></head>
      <body>
        <p>
    """

    if isinstance(list_movie, dict) and len(list_movie) > 0:

        text_content += "SELECTED TORRENTS :\n"
        text_content += "\n------------------------------------------------------------------\n"
        html_content += "<h2>SELECTED TORRENTS :</h2>"
        html_content += "------------------------------------------------------------------"

        for title, torrent_property_list in list_movie.iteritems():

            common_properties = torrent_property_list[0]

            if common_properties['imdb_title'] != "" and common_properties['trust_imdb']:
                text_content += "\n" + common_properties['imdb_title'].upper() + "\n"
                html_content += "<h3>" + common_properties['imdb_title'] + "</h3>"
            else:
                text_content += "\n" + common_properties['title'].upper() + "\n"
                html_content += "<h3>" + common_properties['title'] + "</h3>"

            if 'year' in common_properties:
                text_content += "Year : " + common_properties['year'] + "\n"
                html_content += "Year : " + common_properties['year'] + "<br>"

            if common_properties['imdb_title'] != "":

                text_content += "\n"
                text_content += "IMDB :\n"
                text_content += common_properties['imdb_title'] + " (" + common_properties['imdb_url'] + ")\n"
                text_content += "Rating : " + str(common_properties['rating']) + "\n"
                if common_properties['imdb_plot'].strip() != "":
                    text_content += common_properties['imdb_plot'].strip()
                    text_content += "\n"

                html_content += "<br>"
                html_content += "<a href=\"" + common_properties['imdb_url'] + "\">IMDB Rating : " + str(common_properties['rating']) + "</a><br>"
                if common_properties['imdb_cover_url'] != "":
                    html_content += "<img src=\"" + common_properties['imdb_cover_url'] + "\">"
                if common_properties['imdb_plot'].strip() != "":
                    html_content += common_properties['imdb_plot'].strip()
                    html_content += "<br>"

                if not common_properties['trust_imdb']:
                    text_content += "\n"
                    text_content += "*** WARNING : Approximate IMDB match ***\n"

                    html_content += "<br>"
                    html_content += "<b>*** WARNING : Approximate IMDB match ***</b><br>"

            else:
                text_content += "\n"
                text_content += "NO IMDB MATCH FOUND\n"

                html_content += "<br>"
                html_content += "NO IMDB MATCH FOUND<br>"

            for torrent_properties in torrent_property_list:
                text_content += "\n"
                html_content += "<br>"

                text_content += "Torrent : " + torrent_properties['torrent_file_url'] + "\n"
                html_content += "Torrent : <a href=\"" + torrent_properties['torrent_file_url'] + "\">" + torrent_properties['torrent_title'] + "</a><br>"

                if torrent_properties['size'] is not None:
                    text_content += "Size : " + " ".join(torrent_properties['size']) + "\n"
                    html_content += "Size : " + " ".join(torrent_properties['size']) + "<br>"

                if 'lan' in torrent_properties:
                    text_content += "Language : " + torrent_properties['lan'] + "\n"
                    html_content += "Language : " + torrent_properties['lan'] + "<br>"

            text_content += "\n------------------------------------------------------------------\n"
            html_content += "<br>------------------------------------------------------------------<br>"
    else:
        text_content += "NO SELECTED TORRENTS\n"
        text_content += "\n------------------------------------------------------------------\n"

        html_content += "<h2>NO SELECTED TORRENTS</h2>"
        html_content += "------------------------------------------------------------------<br>"


    if isinstance(list_movie_discarded, dict) and len(list_movie_discarded) > 0:

        text_content += "\n"
        text_content += "DISCARDED TORRENTS :\n"
        text_content += "\n"

        html_content += "<br>"
        html_content += "<h2>DISCARDED TORRENTS :</h2>"

        for title, properties in list_movie_discarded.iteritems():

            text_content += properties['torrent_title'] + " (" + properties['torrent_file_url'] + ")\n"
            text_content += properties['discard'] + "\n"
            text_content += "\n"

            html_content += "<a href=\"" + properties['torrent_file_url'] + "\">" + properties['torrent_title'] + "</a><br>"
            html_content += properties['discard'] + "<br>"
            html_content += "<br>"

    html_content += """
        </p>
      </body>
    </html>
    """

    return html_content, text_content

def prompt(prompt):
    return raw_input(prompt).strip()

def get_config_from_user():
    global config

    console_log("Configuration file not passed to script or invalid.\n")
    console_log(" => Please enter your preferences\n")

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
        config['password'] = prompt('Password: ')
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
                pickle.dump(config, fd)
        except:
            console_log("   An exception occured. Config not saved to file\n")
    console_log("\n")

def get_config():
    global config
    global config_ok

    if len(sys.argv) > 1:
        file_config = sys.argv[1]
    else:
        file_config = None

    if file_config is not None:
        if os.path.exists(file_config):
            try:
                with open(file_config, 'rb') as fd:
                    config = pickle.load(fd)
            except:
                console_log("Error opening config file " + file_config)
        else:
            console_log(file_config + " is not a valid path")

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
    try:
        print unicode(text_content)
    except UnicodeEncodeError:
        ascii_text_content = unicodedata.normalize('NFKD', text_content).encode('ascii', 'ignore')
        print ascii_text_content

def process_report(text_content, html_content):

    global config
    global config_ok
    global script_executed
    global server_connected
    global server

    while not config_ok:
        sleep(1)

    if config['method'] == 'mail':

        if config['mail_format'] == 'html':
            message = MIMEText(html_content, 'html', 'utf-8')
        else:
            message = MIMEText(text_content, 'plain', 'utf-8')

        message['Subject'] = 'Mail from RSS Parser'
        message['From'] = config['from']
        message['To'] = config['to']

        try:
            server = smtplib.SMTP(config['smtp_server'])
            server_connected = True
        except:
            console_log("Unexpected error while connecting to mail server :" + str(sys.exc_info()[0]) + "\n")
            console_log("Printing report to console\n")
            console_log("\n")
            console_log(text_content)

        if server_connected:
            try:
                server.ehlo()
                server.starttls()
                server.login(config['username'], config['password'])
                server.sendmail(config['from'], config['to'], message.as_string())
                server.quit()
                console_log("Report sent by mail\n")
            except:
                console_log("Unexpected error while sending mail :" + str(sys.exc_info()[0]) + "\n")
                console_log("Printing report to console\n")
                console_log("\n")
                console_log(text_content)
            finally:
                server.close()

    else:
        console_log("\n")
        console_log(text_content)

    script_executed = True