import datetime
import matplotlib.dates as pltdates
import matplotlib.pyplot as plt
import pandas as pd
from typing import TypeAlias, Mapping
from zoneinfo import ZoneInfo

class TimePoint():
    """
    A class representing a time point. The time point is a special
    wrapper around a 'datetime.time' that stores all times in UTC
    for working easily with date and times in the library.

    Attributes:
        _time (datetime.time): The inner time object storing the time
            of the time point.
    """

    @staticmethod
    def from_str(time_str: str, tz_str: str):
        """
        Create a TimePoint from a time string.

        Args:
            time_str (str): String containing the time in the format 'HH:MM'.
            ts_str (str): String with the name of a time zone.
        Returns:
            TimePoint: A new TimePoint with the wanted time.
        Raises:
            Exception: In case the time string cannot be converted to a datetime.time.
        """
        tzinfo = ZoneInfo(tz_str)
        time = datetime.datetime.strptime(time_str, "%H:%M").time()
        time = time.replace(tzinfo=tzinfo)
        return TimePoint(time)

    def __init__(self, time: datetime.time) -> None:
        """
        Initialize a TimePoint object.

        Args:
            time (datetime.time): The time object.
        """
        self._time = time

    def __str__(self) -> str:
        return f"{self._time.isoformat()}{self._time.tzinfo}"

    def __repr__(self) -> str:
        return self.__str__()# f"TimePoint(time={self._time.__repr__()})"

    def to_utc_datetime(self, base_dt: datetime.date) -> datetime.datetime:
        """
        Convert the TimePoint into a datetime object combining the underlying
        time with the given date. The new datetime object is converted in UCT.

        Args:
            base_dt (datetime.date): The date object to use.
        Returns:
            datetime.datetime: The new datetime object.
        """
        return datetime.datetime\
            .combine(base_dt, self._time)\
            .astimezone(datetime.UTC)

    def format(self) -> str:
        """
        Returns a string formatted for pretty-print. The string is in the format
        'HH:MM' an is expressed in the timezone it was created.

        Returns:
            str: The formatted string.
        """
        return self._time.strftime("%H:%M")

Table: TypeAlias = pd.DataFrame
"""
Type representing a Table. This type is an alias for a pandas DataFrame.
"""

MTPInfo: TypeAlias = pd.DataFrame
"""
Type representing information about some marked time points. This type
is an alias for pd.DataFrame.

Each row represents the data relative to a marked time point.
The three columns represents:
    - time: datetime object with a time nearest to the time point.
    - value: the value at that time.
    - tp: the marked time point.
"""

QueryDict: TypeAlias = dict[str, str]
"""
Type representing a dictionary used for querying the data in a Table.
The query dictionary is a dict where the keys represents names of
columns of the Table and the values are strings that match exactly
values present in the Table.
"""

def filter_table_by_query(
    table_df: Table,
    query_dict: QueryDict
) -> Table:
    """
    Filter the given table based on the values of given 'query_dict'.
    The values are matched with the data in the table exactly by value (==).

    Args:
        table_df (Table): The table to filter.
        query_dict (dict): A query dictionary.
    Returns:
        Table: The filtered table.
    """
    # no need to filter an empty table
    if table_df.empty:
        return table_df

    query_str = ""
    for i,(k,v) in enumerate(query_dict.items()):
        if i > 0:
            query_str += " and "
        query_str += f"{k}=='{v}'"
    if query_str != "":
        return table_df.query(query_str)
    return table_df

def filter_table_by_range(
    table_df: Table,
    min_tp: TimePoint|None,
    max_tp: TimePoint|None
) -> Table:
    """
    Remove all the rows of a given table where the column _time is outside the range
    given by ['min_tp', 'max_tp'].

    Args:
        table_df (Table): The table to filter.
        min_tp (TimePoint): The minimum time point. Can be None.
        max_tp (TimePoint): The maximum time point. Can be None.
    Returns:
        Table: The filtered table.
    """
    # no need to filter an empty table
    if table_df.empty:
        return table_df

    # get correct min datetime by combining 'min_tp' with the start date
    # if 'min_tp' is None use the start date as minimum
    correct_min_datetime = _table_start_datetime(table_df)
    if min_tp is not None:
        correct_min_datetime = min_tp.to_utc_datetime(
            correct_min_datetime.date())

    # get correct max datetime by combining 'max_tp' with the stop date
    # if 'max_tp' is None use the stop date as maximum
    correct_max_datetime = _table_stop_datetime(table_df)
    if max_tp is not None:
        correct_max_datetime = max_tp.to_utc_datetime(
            correct_max_datetime.date())

    # limit table data inside min and max timestamps
    return table_df[(table_df['_time'] >= correct_min_datetime) \
        & (table_df['_time'] <= correct_max_datetime)]

def compute_approximate_value_of_time_points(
    table_df: Table,
    time_points: list[TimePoint],
    time_delta: int
) -> MTPInfo:
    """
    Given a list of time points, this function computes for each of them the
    approximate value relative to the time point. The approximate value is the
    value of the table with the minimum difference between the _time and the
    time point. The difference is weighted so the distance between the approximate
    value and the time point is at most 'time_delta_min'.

    Args:
        table_df (Table): The table.
        time_points (list[TimePoint]): List of time points.
        time_delta_min (int): A time delta in minutes used to approximate the vale.
    Returns:
        MTPInfo: The object containing info about the marked time points.
    """
    # no approximate value for an empty table
    if table_df.empty:
        return MTPInfo([], columns=['time','value','tp'])

    ret_data_lst = []
    for marked_tp in time_points:
        tp_datetime = marked_tp.to_utc_datetime(_table_start_datetime(table_df))

        # copy the table to a tmp dataframe so we can add a new column without
        # changing the original data.
        tmp_df = table_df[['_time', '_value']].copy()
        tmp_df['_dt'] = abs(table_df['_time'] - tp_datetime)
        near_tp_df = tmp_df[tmp_df['_dt'] < datetime.timedelta(minutes=time_delta)]
        best_match = near_tp_df[near_tp_df['_dt'] == near_tp_df['_dt'].min()]

        if not best_match.empty:
            ret_data_lst.append({
                'time': tp_datetime,
                'value': best_match['_value'].iloc[0],
                'tp': marked_tp
            })
    return MTPInfo(ret_data_lst, columns=['time','value','tp'])\
        .sort_values(['time'])

def plot_table(
    table_df: Table,
    marked_tp_df: MTPInfo,
    title: str = "",
    plot_title: bool = False,
    tz: str = "UTC",
    figsize: tuple[int|float, int|float] = (8,4),
    ylim: tuple|None = None,
    connect_points: bool = True,
    save_path: str = "figure.png",
    save_to_file: bool = False
):
    """
    Plot given table.

    Args:
        table_df (Table): The table to plot.
        marked_tp_df (MTPInfo): The info about marked time points.
        title (str): The title of the plot. This is used only if
            'plot_title' is True.
        plot_title (bool): If True the title is inserted in the plot.
        tz (str): String representing a timezone used to format the
            dates in the plot axis.
        fisize (tiple): A tuple containing exactly two elements: the
            width and height of the plot.
        connect_points (bool): If True the marked time points plotted
            are connected by a line.
        save_path (str): Path where to store the plot. This is used only
            if 'save_to_file' is True.
        save_to_file (bool): If True the plot is saved to file as 'save_path',
            otherwise it's displayed to screen.
    """
    # TODO: We can plot an empty table?
    # no need to plot an empty table
    # if table_df.empty:
        # return

    # make plot
    fig, ax = plt.subplots(figsize=figsize)
    # configure properties
    ax.xaxis.set_major_formatter(pltdates.DateFormatter('%H:%M',tz))
    if plot_title:
        plt.title(title)

    if ylim is not None:
        ax.set_ylim(ylim)
    # ax.autoscale_view()

    # plot main data
    ax.plot(table_df['_time'], table_df['_value'])

    # plot approximate marked time points
    if not marked_tp_df.empty:
        ax.plot(marked_tp_df['time'], marked_tp_df['value'], 'ro')
        if connect_points:
            ax.plot(marked_tp_df['time'], marked_tp_df['value'], 'r')
        for _, val_df in marked_tp_df.iterrows():
                plt.annotate(
                    val_df['tp'].format(),            # this is the text
                    (val_df['time'],val_df['value']), # these are the coordinates to position the label
                    textcoords="offset points",       # how to position the text
                    xytext=(0,10),                    # distance from text to points (x,y)
                    ha='center'                       # horizontal alignment [left, right, center]
                )
    plt.tight_layout()

    # save the plot
    if save_to_file:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()

def _table_start_datetime(table: Table) -> datetime.datetime:
    """
    Get the start datetime from column _start of table.

    Args:
        table (Table): The table.
    Returns:
        datetime: The start datetime.
    """
    return table['_start'].iloc[0].to_pydatetime()

def _table_stop_datetime(table:Table) -> datetime.datetime:
    """
    Get the stop datetime from column _stop of table.

    Args:
        table (Table): The table.
    Returns:
        datetime: The stop datetime.
    """
    return table['_stop'].iloc[0].to_pydatetime()
