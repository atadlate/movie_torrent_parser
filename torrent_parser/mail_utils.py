__author__ = 'mcharbit'

import os
import smtplib
import pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def format_mail(list_movie, list_movie_discarded):

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

def get_config(config):
    if not isinstance(config, dict):
        raise Exception('Parameter must be an instance of dict')

    config['from'] = prompt('From: ')
    config['to'] = prompt('To: ')
    config['smtp_server'] = prompt('SMTP server: ')
    config['username'] = prompt('Username: ')
    config['password'] = prompt('Password: ')
    save = prompt('Would you like to save config to a file ? (Y/N): ')
    if save.lower() == "yes" or save.lower() == "y":
        config_path = prompt('  File path (case sensitive): ')
        try:
            with open(config_path, 'wb') as fd:
                pickle.dump(config, fd)
        except:
            print " An exception occured. Config not saved to file"
    print "\n"

def send_mail(text_content, html_content, file_config=None):

    if (len(text_content) > 0 or len(html_content) > 0):
        config = dict()
        if file_config is not None:
            if os.path.exists(file_config):
                try:
                    with open(file_config, 'rb') as fd:
                        config = pickle.load(fd)
                except:
                    print file_config + " is not a valid config file"
            else:
                print file_config + " is not a valid path"

        if not (config.has_key('username')
                and config.has_key('smtp_server')
                and config.has_key('password')
                and config.has_key('from')
                and config.has_key('to')):
            get_config(config)

        outer_message = MIMEMultipart()
        # outer_message = MIMEMultipart('alternative')
        outer_message['Subject'] = 'Mail from RSS Parser'
        outer_message['From'] = config['from']
        outer_message['To'] = config['to']
        if len(html_content) > 0:
            html_message = MIMEText(html_content, 'html', 'utf-8')
            outer_message.attach(html_message)
        if len(text_content) > 0:
            text_message = MIMEText(text_content, 'plain', 'utf-8')
            # outer_message.attach(text_message)

        server = smtplib.SMTP(config['smtp_server'])

        try:
            server.ehlo()
            server.starttls()
            server.login(config['username'], config['password'])
            server.sendmail(config['from'], config['to'], outer_message.as_string())
            server.quit()

        finally:
            server.close()
