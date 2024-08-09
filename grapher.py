#! python

import os
import sys
import argparse as arg
import logging
from colorlog import ColoredFormatter
from pandas import concat, DataFrame
from flux_csv import ParseError, read_annotated_csv
from graphlib import TimePoint, \
    filter_table_by_query, \
    filter_table_by_range, \
    compute_approximate_value_of_time_points, \
    plot_table

KEEP_COLS = ['_time','_value','_field', 'host','location','room','_start','_stop']
GROUPBY_COLS = ['host','location','room','_field']
LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}
LOGFORMAT = "%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
# LOGFORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

logger = logging.getLogger(__name__)

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

def parse_marked_time_points(marked_tp_strs, tz):
    tps = []
    for tp_str in marked_tp_strs:
        try:
            tps.append(TimePoint.from_str(tp_str, tz))
        except ValueError as ex:
            logger.error(f"Error parsing time point '{tp_str}'. {ex}")
            logger.warning(f"Skip malformed time point '{tp_str}'")
    return tps

def parse_min_max_time_points(min_time_str, max_time_str, tz):
    min_tp = None
    max_tp = None
    if min_time_str is not None:
        try:
            min_tp = TimePoint.from_str(min_time_str, tz)
        except ValueError as ex:
            logger.error(f"Error parsing min time point '{min_time_str}'. {ex}")
            logger.warning(f"Skip malformed min time point '{min_time_str}'")
    if max_time_str is not None:
        try:
            max_tp = TimePoint.from_str(max_time_str, tz)
        except ValueError as ex:
            logger.error(f"Error parsing max time point '{max_time_str}'. {ex}")
            logger.warning(f"Skip malformed max time point '{max_time_str}'")
    return (min_tp, max_tp)

def process_table_group(
    group_info,
    group_df,
    min_time_point,
    max_time_point,
    marked_time_points,
    ylim_range,
    args
):
    plot_title = get_plot_title(group_info)
    logger.info(f"Processing '{plot_title}'...")

    # get approximate data relative to the marked time points
    marked_tp_data = compute_approximate_value_of_time_points(
        group_df,
        marked_time_points,
        args['deltatime']
    )
    logger.debug(
        (f"Using approximate market times "
        f"{[e.strftime('%Y-%m-%d %X') for e in marked_tp_data['time'].to_list()]}"))

    plot_save_path =os.path.join(
        args['output_dir'],
        f"{get_plot_name(group_info)}.png"
    )
    if not args['dry_run']:
        logger.debug(f"Saving plot to '{plot_save_path}'")
    else:
        logger.debug(f"Displaying plot '{plot_title}'")

    # make the plot
    plot_table(
        table_df=group_df,
        marked_tp_df=marked_tp_data,
        title=plot_title,
        plot_title=args['plot_title'],
        tz=args['timezone'],
        figsize=args['plot_size'],
        connect_points=args['connect_plot_points'],
        ylim=ylim_range,
        save_path= plot_save_path,
        save_to_file=(not args['dry_run'])
    )
    return marked_tp_data

def get_plot_title(group_info):
    return f"{group_info[3]} {group_info[0]} {group_info[2]} {group_info[1]}"

def get_plot_name(group_info):
    return f"{group_info[3]}_{group_info[0]}_{group_info[2]}_{group_info[1]}"

def get_yaxes_limits(grouped, use_same_scale):
    # Create a dict where the keys are the fields and the values
    # are couples of (bottom,top) ranges for the y axes.
    # If 'plot_use_same_scale' is False the values are (None,None) and
    # matplotlib will automatically compute the limits.
    yaxis_lim_dict = {}
    if use_same_scale:
        # find min and max values for each field
        for items, values in grouped:
            key = items[3]
            curr_min = values['_value'].min()
            curr_max = values['_value'].max()
            if key not in yaxis_lim_dict:
                yaxis_lim_dict[key] = [curr_min, curr_max]
            else:
                old_min, old_max = yaxis_lim_dict[key]
                if old_min > curr_min:
                    old_min = curr_min
                if old_max < curr_max:
                    old_max = curr_max
                yaxis_lim_dict[key] = [old_min, old_max]
        # add a margin to the min and max values for better plots.
        # The margins are computed as 5% of the data interval as suggested
        # by [this](https://matplotlib.org/devdocs/api/_as_gen/matplotlib.axes.Axes.margins.html).
        yaxis_lim_dict = {k:[
            (v0 - ((v1 - v0) * 0.05)),
            (v1 + ((v1 - v0) *0.05))]
            for k,(v0,v1) in yaxis_lim_dict.items()}
    else:
        for items, values in grouped:
            key = items[3]
            yaxis_lim_dict[key] = None
    return yaxis_lim_dict

def process_data(args):
    # get marked time points
    marked_time_points = parse_marked_time_points(
        args['marked_times'],
        args['timezone']
    )
    logger.debug(f"Using marked time points: {[e.format() for e in marked_time_points]}")

    # get min and max time points
    min_time_point, max_time_point = parse_min_max_time_points(
        args['min_time'],
        args['max_time'],
        args['timezone']
    )
    logger.debug(f"Using {min_time_point=} {max_time_point=}")

    # read tables from csv file
    try:
        table = read_annotated_csv(args["input_file"], merge_tables=True)
        logger.debug(f"Read {len(table)} rows from CSV file")
    except (FileNotFoundError, ParseError) as ex:
        logger.error(ex, exc_info=ex)
        return

    # skip table if it does not have all the required columns
    if not set(KEEP_COLS).issubset(table.columns):
        logger.error(f"Input table is malformed. Missing some of columns {KEEP_COLS}")
        return

    # create a query dict used to filter the table values
    query_dict = {
        'host': args['filter_host'],
        'location': args['filter_location'],
        'room': args['filter_room'],
        '_field': args['filter_field'],
    }
    query_dict = {k:v for k,v in query_dict.items() if v is not None}
    table = filter_table_by_query(table, query_dict)

    # filter time column by min/max range
    table = filter_table_by_range(table, min_time_point, max_time_point)

    # remove unused columns
    table = table[KEEP_COLS]

    # skip table if it's empty after filtering
    if table.empty:
        logger.warning(f"The table is empty. Nothing to do.")
        return

    # group rows of table by sensor type
    grouped_table = table.groupby(GROUPBY_COLS)

    # print table groups info
    a=[{'host': v[0],'location':v[1],'room':v[2],'field':v[3]}
        for v,_ in grouped_table]
    logger.debug("Found the following elements:")
    [logger.debug(l) for l in DataFrame(a).to_string(index=False).split('\n')]

    # Create y-axes limits dict
    yaxis_lim_dict = get_yaxes_limits(grouped_table, args['plot_use_same_scale'])
    logger.debug(f"{yaxis_lim_dict=}")

    # loop each grouped table
    cumulative_mtpinfo = []
    for group_info, group_df in grouped_table:
        mtpinfo = process_table_group(
            group_info,
            group_df,
            min_time_point,
            max_time_point,
            marked_time_points,
            yaxis_lim_dict[group_info[3]],
            args
        )
        mtpinfo['tp'] = mtpinfo['tp'].map(lambda e: e.format())
        cumulative_mtpinfo.append(
            mtpinfo[['tp','value']].rename(
                columns={
                    "tp": "time",
                    "value": get_plot_name(group_info)
                }).set_index('time')
        )

    # create a cumulative mtpinfo dataframe
    cumulative_df = concat(cumulative_mtpinfo,axis=1)
    logger.debug(f"Produced {cumulative_df.head()=}")
    # store cumulative dataframe to file
    if not args['dry_run'] and args['save_marked_tp_data']:
        cum_file_path = os.path.join(
            args['output_dir'],
            args['marked_tp_file_name']
        )
        cumulative_df.to_csv(cum_file_path)
        logger.info(f"Saved marked time point data to '{cum_file_path}'")

def main():
    # parse cli arguments
    cli_args = parse_cli_args()
    args = vars(cli_args)

    # init the main logger
    init_logger(args['verbose'])
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
