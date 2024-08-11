import os
import logging
from pandas import DataFrame, concat
from colorlog import ColoredFormatter
from grapher.flux_csv import read_annotated_csv, ParseError
from grapher.graphlib import TimePoint, \
    compute_approximate_value_of_time_points, \
    filter_table_by_query, \
    filter_table_by_range, \
    plot_table, \
    get_yaxes_limits

KEEP_COLS = ['_time','_value','_field', 'host','location','room','_start','_stop']
GROUPBY_COLS = ['host','location','room','_field']

logger = logging.getLogger('grapher')

def get_plot_title(group_info):
    return f"{group_info[3]} {group_info[0]} {group_info[2]} {group_info[1]}"

def get_plot_name(group_info):
    return f"{group_info[3]}_{group_info[0]}_{group_info[2]}_{group_info[1]}"

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

def query_dict_from_args(args):
    # create a query dict from data in the args
    query_dict = {
        'host': args['filter_host'],
        'location': args['filter_location'],
        'room': args['filter_room'],
        '_field': args['filter_field'],
    }
    return {k:v for k,v in query_dict.items() if v is not None}

def print_group_info(grouped_table):
    a=[{'host': v[0],'location':v[1],'room':v[2],'field':v[3]}
        for v,_ in grouped_table]
    logger.debug("Found the following elements:")
    [logger.debug(l) for l in DataFrame(a).to_string(index=False).split('\n')]

def plot_table_group(
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
    table = filter_table_by_query(table, query_dict_from_args(args))

    # filter time column by min/max range
    table = filter_table_by_range(table, min_time_point, max_time_point)

    # remove unused columns
    table = table[KEEP_COLS]

    # skip table if it's empty after filtering
    if table.empty:
        logger.warning(f"The table is empty. Nothing to do.")
        return
    # Create y-axes limits dict
    yaxis_lim_dict = get_yaxes_limits(table, args['plot_use_same_scale'])
    logger.debug(f"{yaxis_lim_dict=}")

    # group rows of table by sensor type
    grouped_table = table.groupby(GROUPBY_COLS)

    # print table groups info
    print_group_info(grouped_table)

    # loop each grouped table
    cumulative_mtpinfo = []
    for group_info, group_df in grouped_table:
        mtpinfo = plot_table_group(
            group_info,
            group_df,
            min_time_point,
            max_time_point,
            marked_time_points,
            yaxis_lim_dict[group_info[3]],
            args
        )
        # transform mtpinfo in a format we want to store
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
