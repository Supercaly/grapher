#! python

import os
from datetime import datetime, timedelta
from dateutil import parser, tz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import argparse as arg

ap = arg.ArgumentParser(description='''
                        Create automatically plots from data stored inside InfluxDB. 
                        This tool is intended to be used to produce plots in an automated and 
                        consistent way from data supplied in csv format and obtained from InfluxDB.
                        ''')
ap.add_argument("csv_file", 
                type=arg.FileType('r'),
                help="the csv file with the influx data to load")
ap.add_argument("-t","--highlights",
                action="append",
                default=[],
                help="specify a list of hours (format HH:MM) to be highlighted in the graphs")
ap.add_argument("--title",
                action='store_true',
                default=False,
                help="display the main title in the graph")
ap.add_argument("--min",
                type=str,
                default=None,
                help="specify a minimum hour (format HH:MM) to start the graphs")
ap.add_argument("--max",
                type=str,
                default=None,
                help="specify a maximum hour (format HH:MM) to start the graphs")
ap.add_argument("-o", "--outdir",
                type=str,
                default=".",
                help="path to the folder where the produced graphs are stored")
ap.add_argument("--dry-run",
                action='store_true',
                default=False,
                help="perform a dry run showing the graphs to screen without storing anything")
args = ap.parse_args()

times_highlights = args.highlights
time_fmt = '%H:%M'
mytz = tz.gettz("Europe/Rome")

if args.dry_run:
    print("performing dry run")

# get time highlights
times_highlights = [datetime.strptime(t, time_fmt).time() for t in times_highlights]
print(f"using time highlights: {[e.strftime(time_fmt) for e in times_highlights]}")

# create outdir if not exists
if not args.dry_run and not os.path.exists(args.outdir):
    print(f"creating output dir '{args.outdir}'")
    os.makedirs(args.outdir, exist_ok=True)

##########################################
# parse csv file to extract relevant data
##########################################
raw_data=[]
lines = args.csv_file.readlines()

header=None
i = 0
while i < len(lines):
    line = lines[i]
    line = line.replace('\n','')

    if len(line) == 0:
        i += 1
        continue

    if line.startswith('#'):
        i += 3
        line = lines[i]
        line = line.replace('\n','')
        header = line.split(',')
        # print(f"header: {header}")
        i += 1
        continue

    assert header is not None, "csv header was not read"

    split_line = line.split(',')
    tmp_list = []
    tmp_list.append(int(split_line[header.index('table')]))
    tmp_list.append(split_line[header.index('_field')])

    time_string = split_line[header.index('_time')]
    timestamp = parser.parse(time_string).astimezone(mytz)
    tmp_list.append(timestamp)
    
    tmp_list.append(float(split_line[header.index('_value')]))
    tmp_list.append(split_line[header.index('host')])
    tmp_list.append(split_line[header.index('location')])
    tmp_list.append(split_line[header.index('room')])
    raw_data.append(tmp_list)

    i += 1
# print(raw_data)

#################################
# group raw_data by table. 
# Each table will became a chart
#################################
grouped_data={}
for d in raw_data:
    id = d[0]
    grouped_data.setdefault(id,[]).append(d)
grouped_data = list(grouped_data.values())
# print(grouped_data)

###################
# create the plots
###################
for chart_data in grouped_data:
    field = chart_data[0][1]
    host = chart_data[0][4]
    loc = chart_data[0][5]
    room = chart_data[0][6]

    print(f"producing plot '{room} {loc} {host} - {field}'")
    
    # get min and max times to plot
    if args.min is not None:
        min_time = datetime.strptime(args.min, time_fmt).time()
        min_date = datetime.combine(chart_data[0][2].date(), min_time).astimezone(mytz)
    else:
        min_date = min([f[2] for f in chart_data])
    if args.max is not None:
        max_time = datetime.strptime(args.max, time_fmt).time()
        max_date = datetime.combine(chart_data[0][2].date(), max_time).astimezone(mytz)
    else:
        max_date = max([f[2] for f in chart_data])

    # filter only the data inside min and max times
    times = []
    values = []
    for i in range(len(chart_data)):
        if (chart_data[i][2] >= min_date) and (chart_data[i][2] <= max_date):
            times.append(chart_data[i][2])
            values.append(chart_data[i][3])
    
    # extract the index of the data to highlight
    current_date = chart_data[0][2].date()
    highlight_idxs = []
    highlight_label = []
    for th in times_highlights:
        dth = datetime.combine(current_date, th).astimezone(mytz)
        idx = np.argmin(list([abs(d - dth) for d in times]))
        
        if abs(times[idx] - dth) < timedelta(minutes=30):
            highlight_idxs.append(idx)
            highlight_label.append(th.strftime(time_fmt))
        else:
            print(f"skipping time highlight: {th.strftime(time_fmt)}")
    highlight_idxs.sort()
    highlight_label.sort()
    print(f"using approximated time highlights: {[times[e].time().strftime(time_fmt) for e in highlight_idxs]}")

    # make the plot   
    fig, ax = plt.subplots(figsize=(8,4.5))
    
    if args.title:
        chart_title = f"{field} - {host} - {room} {loc}"
        plt.title(chart_title)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(time_fmt,mytz))

    ax.plot(times,values)

    # plot highlights
    x_highlight = [f for i, f in enumerate(times) if i in highlight_idxs]
    y_highlight = [f for i, f in enumerate(values) if i in highlight_idxs]
    ax.plot(x_highlight, y_highlight,'r',x_highlight, y_highlight,'ro')
    
    # ax.xaxis.set_major_locator(mdates.HourLocator())
    # ax.xaxis.set_minor_locator(ticker.FixedLocator(x_highlight))

    # add highlights annotations
    for label,x,y in zip(highlight_label,x_highlight,y_highlight):
        plt.annotate(label, # this is the text
                    (x,y), # these are the coordinates to position the label
                    textcoords="offset points", # how to position the text
                    xytext=(0,10), # distance from text to points (x,y)
                    ha='center') # horizontal alignment can be left, right or center

    plt.tight_layout()

    # save the plot
    if not args.dry_run:
        fig_name = f"{field}_{host}_{room}_{loc}.png"
        fig_path = os.path.join(args.outdir,fig_name)
        plt.savefig(fig_path)
    else:
        plt.show()
    # break