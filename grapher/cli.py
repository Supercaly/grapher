#! python

import os
import sys
import argparse as arg
import logging
from colorlog import ColoredFormatter
from pandas import concat, DataFrame
from grapher.process import process_data

LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}
LOGFORMAT = "%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
# LOGFORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logger = logging.getLogger('grapher')

def init_logger(verbose: bool):
    formatter = ColoredFormatter(LOGFORMAT, log_colors=LOG_COLORS)
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def parse_cli_args():
    ap = arg.ArgumentParser(description=
        '''
        Generate plots automatically from data stored in InfluxDB database.
        This tool is designed to consistently produce plots from CSV files
        produced by InfluxDB.
        ''')
    ap.add_argument(
        'input_file',
        help='''
            The file with the data to use for the plots.
            The file is and annotated CSV produced by InfluxDB with all the
            data divided in one or more tables.
            '''
    )
    ap.add_argument(
        '-n','--dry-run',
        dest='dry_run',
        action='store_true',
        help='Perform a dry run without saving anything to disk.'
    )
    ap.add_argument(
        '-v','--verbose',
        action='store_true',
        help='Be verbose.'
    )
    ap.add_argument(
        '-m','--marked-times',
        dest='marked_times',
        action='append',
        default=[],
        help='''
            A list of time points (in the format HH:MM) that we want to
            highlighted in the plots.
            '''
    )
    ap.add_argument(
        '--min','--min-time',
        dest='min_time',
        type=str,
        default=None,
        help='Set a minimum start time for the plots (in the format HH:MM).'
    )
    ap.add_argument(
        '--max','--max-time',
        dest='max_time',
        type=str,
        default=None,
        help='Set a maximum stop time for the plots (in the format HH:MM).'
    )
    ap.add_argument(
        '-o','--output-dir',
        dest='output_dir',
        type=str,
        default='.',
        help='Path to a folder where the generated plots are stored.'
    )
    ap.add_argument(
        '--save-marked-data',
        dest='save_marked_tp_data',
        action=arg.BooleanOptionalAction,
        default=True,
        help='Store the values corresponding to the marked times to a file.'
    )
    ap.add_argument(
        '-f','--marked-file',
        dest='marked_tp_file_name',
        type=str,
        default='marked_data.txt',
        help='''
            The name of the file where the values of the marked times are stored.
            By default this file is saved inside the output dir.
            '''
    )
    ap.add_argument(
        '--tz','--timezone',
        dest='timezone',
        type=str,
        default="Europe/Rome",
        help='''
            Specify the timezone for all provided times, except for the input
            file, which is always assumed to be in UTC.

            By default this uses the Europe/Rome timezone for all times.
            '''
    )
    ap.add_argument(
        '--dt','--deltatime',
        dest='deltatime',
        type=int,
        default=10,
        help='''
            A number expressing the range of time (in minutes) used when finding
            the approximate value of a marked time.

            When passing a marked time there is no guarantee that will exist a point
            in the data with the exact same time. For this reason when we assign a value
            to a marked time we search for a time near it. The deltatime is used to restrict
            the search to only times + or - deltatime minutes around it.

            This parameter already has a sane defalut and, in general there is no need to
            change it.
            '''
    )
    ap.add_argument(
        '--host',
        dest='filter_host',
        type=str,
        default=None,
        help='''
            Filter the data keeping only the values where the host column matches given value.
            '''
    )
    ap.add_argument(
        '--location',
        dest='filter_location',
        type=str,
        default=None,
        help='''
            Filter the data keeping only the values where the location column matches given value.
            '''
    )
    ap.add_argument(
        '--room',
        dest='filter_room',
        type=str,
        default=None,
        help='''
            Filter the data keeping only the values where the room column matches given value.
            '''
    )
    ap.add_argument(
        '--field',
        dest='filter_field',
        type=str,
        default=None,
        help='''
            Filter the data keeping only the values where the field column matches given value.
            '''
    )
    ap.add_argument(
        '--title',
        dest='plot_title',
        action=arg.BooleanOptionalAction,
        default=True,
        help='Display the main title in the plots.'
    )
    ap.add_argument(
        '--size',
        dest='plot_size',
        type=float,
        nargs=2,
        default= [8,4.5],
        help='Size of the plots expressed in width and height (W H).'
    )
    ap.add_argument(
        '--connect',
        dest='connect_plot_points',
        action=arg.BooleanOptionalAction,
        default=True,
        help='''
            The marked times that are highlighted in the plots will
            be connected to one another with a line.

            With --no-connect_points no line will be displayed.
            '''
    )
    ap.add_argument(
        '-u', '--use-same-scale',
        dest='plot_use_same_scale',
        default=False,
        action='store_true',
        help='''
            This option will use the same scale for the y-axis while creating
            plots that have the same field.

            By default each plot is in autoscale mode, mening that the axis limits
            are determined based only on the data of that plot. This option will
            compute the best range of values for plots with the same field and use
            that for each plot easying the comparison between plots.
        '''
    )

    # TODO: Add parameters to customize plot appearance
    return ap.parse_args()

def main():
    # parse cli arguments
    cli_args = parse_cli_args()
    args = vars(cli_args)

    # init the main logger
    init_logger(args['verbose'])
    # logger = logging.getLogger('grapher')
    logger.debug(f"{args=}")

    if args["dry_run"]:
        logger.info("Performing dry run...")

    logger.debug(f"Using timezone '{args['timezone']}'")

    # create outdir if not exists
    if not args["dry_run"] and not os.path.exists(args["output_dir"]):
        logging.debug(f"Creating output directory '{args['output_dir']}'")
        os.makedirs(args["output_dir"], exist_ok=True)

    process_data(args)

if __name__ == "__main__":
    main()
