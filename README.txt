Handy parser going through RSS provided by torrent sites, selecting movies with proper encoding and IMDB rating,
retrieving other useful info from IMDb and sending a digest by mail

Usage :

    torrent_parser [config_file] [-b] [-l log_file]

If config_file is not passed or invalid, the script will prompt you for the settings, let you save them to a file for future use, and let you schedule an automatic run with the defined configuration

If -b option is passed, script will run in background. In this mode, if configuration is missing or invalid, the script won't prompt you for preferences and will consider a fatal error. This is the mode used during auto-run

If -l option is passed, logs are written to the log_file passed as argument instead of stdout. If log_file isn't given or doesn't exist, a default log file named parser_log.txt in the package distribution is used
