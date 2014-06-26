__author__ = 'mcharbit'

import sys
import smtplib
from email.mime.text import MIMEText
from time import sleep
import config

server_connected = False
server = None

def format_report(list_movie, list_movie_discarded):

    html_content = text_content = u""

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

        for key, torrent_property_list in list_movie.iteritems():

            common_properties = torrent_property_list[0]

            if common_properties['imdb_title'] != "" and common_properties['trust_imdb']:
                text_content += "\n" + common_properties['imdb_title'].upper() + "\n"
                html_content += "<h3>" + common_properties['imdb_title'] + "</h3>"
            else:
                text_content += "\n" + common_properties['title'].upper() + "\n"
                html_content += "<h3>" + common_properties['title'] + "</h3>"

            if 'year' in common_properties:
                text_content += "Year : " + common_properties['year'] + "\n"
                text_content += "\n"
                html_content += "Year : " + common_properties['year'] + "<br>"
                html_content += "<br>"

            if common_properties['imdb_title'] != "":

                # TEXT
                text_content += "IMDB :\n"
                text_content += common_properties['imdb_title'] + " (" + common_properties['imdb_url'] + ")\n"
                text_content += "Rating : " + str(common_properties['rating']) + "\n"
                if common_properties['imdb_plot'].strip() != "":
                    text_content += common_properties['imdb_plot'].strip()
                    text_content += "\n"
                if common_properties['imdb_genres'] != "":
                    text_content += "Genre : " + common_properties['imdb_genres'] + "\n"
                if common_properties['imdb_countries'] != "":
                    text_content += "Country : " + common_properties['imdb_countries'] + "\n"
                if common_properties['imdb_directors'] != "":
                    text_content += "Director : " + common_properties['imdb_directors'] + "\n"
                if common_properties['imdb_main_cast'] != "":
                    text_content += "Main cast : " + common_properties['imdb_main_cast'] + "\n"
                text_content += "\n"

                # HTML
                html_content += "<a href=\"" + common_properties['imdb_url'] + "\">IMDB Rating : " + str(common_properties['rating']) + "</a><br>"
                # Create a table, with picture on the left (if provided) and properties on the right.
                html_content += "<table>"

                open_tr = False
                if common_properties['imdb_cover_url'] != "":
                    # Determine table dim for picture rowspan
                    list_attributes = ['imdb_genres', 'imdb_countries', 'imdb_directors', 'imdb_main_cast', 'imdb_plot']
                    nb_row = [1 if common_properties[attribute].strip() != "" else 0 for attribute in list_attributes].count(1) + 1
                    html_content += "<tr><td rowspan=\"" + str(nb_row) + "\">"
                    html_content += "<img src=\"" + common_properties['imdb_cover_url'] + "\"></td>"
                    open_tr = True

                if common_properties['imdb_plot'].strip() != "":
                    if not open_tr: html_content += "<tr>"
                    html_content += "<td>" + common_properties['imdb_plot'].strip() + "</td></tr>"
                    open_tr = False

                if not open_tr: html_content += "<tr>"
                html_content += "<td></td></tr>"

                if common_properties['imdb_genres'] != "":
                    html_content += "<tr><td>Genre : " + common_properties['imdb_genres'] + "</td></tr>"
                if common_properties['imdb_countries'] != "":
                    html_content += "<tr><td>Country : " + common_properties['imdb_countries'] + "</td></tr>"
                if common_properties['imdb_directors'] != "":
                    html_content += "<tr><td>Director : " + common_properties['imdb_directors'] + "</td></tr>"
                if common_properties['imdb_main_cast'] != "":
                    html_content += "<tr><td>Main cast : " + common_properties['imdb_main_cast'] + "</td></tr>"

                html_content += "</table>"
                html_content += "<br>"

                if not common_properties['trust_imdb']:
                    text_content += "*** WARNING : Approximate IMDB match ***\n"
                    text_content += "\n"

                    html_content += "<b>*** WARNING : Approximate IMDB match ***</b><br>"
                    html_content += "<br>"

            else:
                text_content += "NO IMDB MATCH FOUND\n"
                text_content += "\n"
                html_content += "NO IMDB MATCH FOUND<br>"
                html_content += "<br>"

            list_digest_torrent = []
            for torrent_properties in torrent_property_list:

                torrent_tuple = (torrent_properties['torrent_title'], torrent_properties['size'])
                # There are chances the same torrent is listed twice, especially when RSS feeds are parsed from multiple sources,
                # Filter similar torrents in name and size
                if not torrent_tuple in list_digest_torrent:
                    list_digest_torrent.append(torrent_tuple)

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

        for key, properties in list_movie_discarded.iteritems():

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

def process_report(text_content, html_content):

    global server_connected
    global server

    if config.config['method'] == 'mail':

        if config.config['mail_format'] == 'html':
            message = MIMEText(html_content, 'html', 'utf-8')
        else:
            message = MIMEText(text_content, 'plain', 'utf-8')

        message['Subject'] = 'Movies torrents digest'
        message['From'] = config.config['from']
        message['To'] = config.config['to']

        try:
            server = smtplib.SMTP(config.config['smtp_server'])
            server_connected = True
        except:
            config.log_message("Unexpected error while connecting to mail server:" + str(sys.exc_info()[0]), 'error')
            config.log_message("Printing report to console\n")
            config.console_log("\n")
            config.console_log(text_content)

        if server_connected:
            try:
                server.ehlo()
                server.starttls()
                server.login(config.config['username'], config.config['password'])
                server.sendmail(config.config['from'], config.config['to'], message.as_string())
                server.quit()
                config.log_message("Report sent by mail")
            except:
                config.log_message("Unexpected error while sending mail :" + str(sys.exc_info()[0]), 'error')
                config.log_message("Printing report to console")
                config.console_log("\n")
                config.console_log(text_content)
            finally:
                server.close()

    else:
        config.console_log("\n")
        config.console_log(text_content)
