import argparse
import json
import os

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

import process

dir_path = os.path.dirname(os.path.realpath(__file__))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--plots', nargs='+', help='''
                        One or more plots to be shown.
                        Available: latency, throughput, overhead, messages, wants, tcp.
                        ''')
    parser.add_argument('-o', '--outputs', nargs='+', help='''
                        One or more outputs to be shown.
                        Available: data
                        ''')
    parser.add_argument('-dir', '--dir', type=str, help='''
                        Result directory to process
                        ''')

    return parser.parse_args()


def process_metric_line(line, experiment_id):
    line = json.loads(line)
    name = line["name"].split('/')
    value = (line["measures"])["value"]
    # set default values
    item = {'eavesCount': 0, 'exType': 'trickle', 'dialer': 'edge', 'tricklingDelay': 0}
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    # for compatibility with old results
    if 'topology' in item:
        item['eavesCount'] = item['topology'].split('-')[-1][0]
    item["value"] = value
    item['experiment'] = experiment_id
    return item


def aggregate_metrics(results_dir):
    res = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "results.out":
                # print (filepath)
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for l in result_file.readlines():
                    res.append(process_metric_line(l, experiment_id))
    return res, len(os.listdir(results_dir))


def groupBy(agg, metric):
    res = {}
    for item in agg:
        if not item[metric] in res:
            res[item[metric]] = []
        res[item[metric]].append(item)
    return res


def autolabel(ax, rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')


def create_ttf_dataframe(metrics, eaves_count, filter_outliers=True):
    outlier_threshold = 2

    overall_frame = pd.DataFrame(columns=['x', 'y', 'tc'])
    averages = list()

    by_ex_type = groupBy(metrics, 'exType')
    for ex_type, ex_type_items in by_ex_type.items():
        by_latency = process.groupBy(ex_type_items, "latencyMS")
        by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
        for latency, latency_items in by_latency:
            by_filesize = process.groupBy(latency_items, "fileSize")
            by_filesize = sorted(by_filesize.items(), key=lambda x: int(x[0]))
            for filesize, filesize_items in by_filesize:
                by_trickling_delay = process.groupBy(filesize_items, "tricklingDelay")
                by_trickling_delay = sorted(by_trickling_delay.items(), key=lambda x: int(x[0]))

                x = []
                labels = []
                y = {}
                tc = {}

                for delay, values in by_trickling_delay:
                    x.append(int(delay))
                    labels.append(int(delay))

                    y[delay] = []
                    tc[delay] = []
                    for i in values:
                        if i["nodeType"] == "Leech":
                            if i["meta"] == "time_to_fetch":
                                y[delay].append(i["value"])
                            if i["meta"] == "tcp_fetch":
                                tc[delay].append(i["value"])

                    avg = []
                    # calculate average first for outlier detection
                    for i in y:
                        scaled_y = [i / 1e6 for i in y[i]]
                        if len(scaled_y) > 0:
                            avg.append(sum(scaled_y) / len(scaled_y))
                        else:
                            avg.append(0)

                    for index, i in enumerate(y.keys()):
                        last_delay = i
                        scaled_y = [i / 1e6 for i in y[i]]
                        # Replace outliers with average
                        if filter_outliers:
                            scaled_y = [i if i < avg[index] * outlier_threshold else avg[index] for i in scaled_y]

                    avg_tc = []
                    for i in tc:
                        scaled_tc = [i / 1e6 for i in tc[i]]
                        if len(scaled_tc) > 0:
                            avg_tc.append(sum(scaled_tc) / len(scaled_tc))
                        else:
                            avg_tc.append(0)

                    test = pd.DataFrame({'x': [int(last_delay)] * len(scaled_y), 'y': scaled_y, 'tc': scaled_tc,
                                         'Latency': [latency + ' ms'] * len(scaled_y),
                                         'File Size': [filesize + ' bytes'] * len(scaled_y),
                                         'Experiment Type': [ex_type] * len(scaled_y),
                                         'Eaves Count': [eaves_count] * len(scaled_y)})
                    overall_frame = pd.concat([overall_frame, test])

                averages.append(
                    {'x': x, 'avg_normal': avg, 'avg_tc': avg_tc, 'eaves_count': eaves_count, 'latency': latency,
                     'filesize': filesize})

    return overall_frame, averages


def get_color_for_index(index, palette):
    return palette[index % len(palette)]


def plot_time_to_fetch_per_extype(df, combined_averages):
    df.sort_values(by=['Eaves Count'], inplace=True)

    plt.figure(figsize=(15, 15))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})
    # palette = sns.color_palette("bright", 10)
    palette = ['r', 'g']
    g = sns.FacetGrid(df, hue='Experiment Type', col="File Size", palette=palette,
                      row="Latency", margin_titles=True)
    g.map(sns.scatterplot, "x", "y", alpha=0.5)

    # Draw the averages onto the plots
    # The flatiter is used to iterate over all axes in the facetgrid
    flatiter = g.axes.flat
    for ax in flatiter:
        index = flatiter.index - 1
        for idx, averages in enumerate(combined_averages):
            ax_latency, ax_filesize = list(g.axes_dict.keys())[index]
            # convert to ints for comparison
            ax_latency = int(ax_latency.split(' ')[0])
            ax_filesize = int(ax_filesize.split(' ')[0])
            # check if the current plot is the one we want to draw the averages on
            is_targeted = int(averages['latency']) == ax_latency and int(averages['filesize']) == ax_filesize
            if is_targeted:
                average_to_draw = averages
                color = get_color_for_index(idx, palette)
                ax.plot(average_to_draw['x'], average_to_draw['avg_normal'],
                        label=f"Protocol fetch - {average_to_draw['eaves_count']} eaves", color=color)
                ax.plot(average_to_draw['x'], average_to_draw['avg_tc'], label="TCP fetch", color='k')

    g.set(xlabel='Trickling delay (ms)', ylabel='Time to Fetch (ms)')
    g.add_legend()

    sns.despine(offset=10, trim=False)


# Parameters
# ----------
# df : dataframe consisting of the data to be plotted
# combined_averages : list of dictionaries containing the average values for each eavesdropper count
def plot_time_to_fetch_for_all_eavescounts(df, combined_averages):
    # sort combined averages by eavesdropper count ascending
    combined_averages = sorted(combined_averages, key=lambda x: x[0]['eaves_count'])
    df.sort_values(by=['Eaves Count'], inplace=True)

    # replace eavesdropper 0 with 'baseline' for better readability
    df['Eaves Count'] = df['Eaves Count'].replace('0', 'baseline')

    plt.figure(figsize=(15, 15))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})
    # palette = sns.color_palette("bright", 10)
    palette = ['r', 'g', 'b', 'y']
    g = sns.FacetGrid(df, hue='Eaves Count', col="File Size", palette=palette,
                      row="Latency", margin_titles=True)
    g.map(sns.scatterplot, "x", "y", alpha=0.5)

    # Draw the averages onto the plots
    # The flatiter is used to iterate over all axes in the facetgrid
    flatiter = g.axes.flat
    for ax in flatiter:
        index = flatiter.index - 1
        for idx, averages in enumerate(combined_averages):
            # check if the current plot is the one we want to draw the averages on
            ax_latency, ax_filesize = list(g.axes_dict.keys())[index]
            # convert to ints for comparison
            ax_latency = int(ax_latency.split(' ')[0])
            ax_filesize = int(ax_filesize.split(' ')[0])
            targeted_averages = [i for i in averages if
                                 int(i['latency']) == ax_latency and int(i['filesize']) == ax_filesize]
            if len(targeted_averages) > 0:
                # we can assume that there is only one item in the list
                average_to_draw = targeted_averages[0]
                color = get_color_for_index(idx, palette)
                ax.plot(average_to_draw['x'], average_to_draw['avg_normal'],
                        label=f"Protocol fetch - {average_to_draw['eaves_count']} eaves", color=color)
                # don't draw the tcp fetch average if eavesdropper count is 0
                if average_to_draw['eaves_count'] != '0':
                    ax.plot(average_to_draw['x'], average_to_draw['avg_tc'], label="TCP fetch", color='k')
                # ax.legend()

    g.set(xlabel='Trickling delay (ms)', ylabel='Time to Fetch (ms)')
    # plt.suptitle("Time to fetch for topology " + topology)
    g.add_legend()

    sns.despine(offset=10, trim=False)


def plot_time_to_fetch_grouped_with_filesize(eaves_count, by_latency, filter_outliers=True):
    # percentage that is multiplied with average to identify outliers
    outlier_threshold = 2

    # Index for subplots
    p_index = 1
    p1, p2 = 1, 1

    fig = plt.figure(figsize=(15, 15))

    axes = list()

    by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
    for latency, latency_items in by_latency:
        by_filesize = process.groupBy(latency_items, "fileSize")
        by_filesize = sorted(by_filesize.items(), key=lambda x: int(x[0]))
        p1 = len(by_latency) if len(by_latency) > 1 else p1
        for filesize, filesize_items in by_filesize:
            p2 = len(by_filesize) if len(by_filesize) > p2 else p2
            by_trickling_delay = process.groupBy(filesize_items, "tricklingDelay")
            by_trickling_delay = sorted(by_trickling_delay.items(), key=lambda x: int(x[0]))

            ax = plt.subplot(p1, p2, p_index, sharey=axes[0] if len(axes) > 0 else None)
            axes.append(ax)
            x = []
            labels = []
            y = {}
            tc = {}

            for delay, values in by_trickling_delay:
                x.append(int(delay))
                labels.append(int(delay))

                y[delay] = []
                tc[delay] = []
                for i in values:
                    if i["nodeType"] == "Leech":
                        if i["meta"] == "time_to_fetch":
                            y[delay].append(i["value"])
                        if i["meta"] == "tcp_fetch":
                            tc[delay].append(i["value"])

                avg = []
                # calculate average first for outlier detection
                for i in y:
                    scaled_y = [i / 1e6 for i in y[i]]
                    if len(scaled_y) > 0:
                        avg.append(sum(scaled_y) / len(scaled_y))
                    else:
                        avg.append(0)

                for index, i in enumerate(y.keys()):
                    scaled_y = [i / 1e6 for i in y[i]]
                    # Replace outliers with average
                    if filter_outliers:
                        scaled_y = [i if i < avg[index] * outlier_threshold else avg[index] for i in scaled_y]
                    ax.scatter([int(i)] * len(y[i]), scaled_y, marker="+")

                avg_tc = []
                for i in tc:
                    scaled_tc = [i / 1e6 for i in tc[i]]
                    ax.scatter([int(i)] * len(tc[i]), scaled_tc, marker="*")
                    if len(scaled_tc) > 0:
                        avg_tc.append(sum(scaled_tc) / len(scaled_tc))
                    else:
                        avg_tc.append(0)

                # print(y)
            ax.plot(x, avg, label="Protocol fetch")
            ax.plot(x, avg_tc, label="TCP fetch")

            ax.set_xlabel('Trickling Delay (ms)')
            ax.set_ylabel('Time-to-Fetch (ms)')
            ax.set_title("Latency: " + latency + "ms , File Size: " + filesize + " bytes")
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.grid()
            ax.legend()

            p_index += 1

        plt.suptitle(f"Time-to-Fetch for different trickling delays, file sizes and topology {eaves_count}")
        plt.tight_layout(h_pad=2, w_pad=4)
        # fig.tight_layout(rect=[0,0,.8,0.8])
        plt.subplots_adjust(top=0.94)


def plot_time_to_fetch_grouped(topology, by_latency, filter_outliers=True):
    # percentage that is multiplied with average to identify outliers
    outlier_threshold = 2

    p1, p2 = len(by_latency), 1
    p_index = 1

    fig = plt.figure(figsize=(15, 15))

    axes = list()

    by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
    for latency, latency_items in by_latency:
        by_trickling_delay = process.groupBy(latency_items, "tricklingDelay")
        by_trickling_delay = sorted(by_trickling_delay.items(), key=lambda x: int(x[0]))

        ax = plt.subplot(p1, p2, p_index, sharey=axes[0] if len(axes) > 0 else None)
        axes.append(ax)
        x = []
        labels = []
        y = {}
        tc = {}

        for delay, values in by_trickling_delay:
            x.append(int(delay))
            labels.append(int(delay))

            y[delay] = []
            tc[delay] = []
            for i in values:
                if i["nodeType"] == "Leech":
                    if i["meta"] == "time_to_fetch":
                        y[delay].append(i["value"])
                    if i["meta"] == "tcp_fetch":
                        tc[delay].append(i["value"])

            avg = []
            # calculate average first for outlier detection
            for i in y:
                scaled_y = [i / 1e6 for i in y[i]]
                if len(scaled_y) > 0:
                    avg.append(sum(scaled_y) / len(scaled_y))
                else:
                    avg.append(0)

            for index, i in enumerate(y.keys()):
                scaled_y = [i / 1e6 for i in y[i]]
                # Replace outliers with average
                if filter_outliers:
                    scaled_y = [i if i < avg[index] * outlier_threshold else avg[index] for i in scaled_y]
                ax.scatter([int(i)] * len(y[i]), scaled_y, marker="+")

            avg_tc = []
            for i in tc:
                scaled_tc = [i / 1e6 for i in tc[i]]
                ax.scatter([int(i)] * len(tc[i]), scaled_tc, marker="*")
                if len(scaled_tc) > 0:
                    avg_tc.append(sum(scaled_tc) / len(scaled_tc))
                else:
                    avg_tc.append(0)

            # print(y)
        ax.plot(x, avg, label="Protocol fetch")
        ax.plot(x, avg_tc, label="TCP fetch")

        ax.set_xlabel('Trickling Delay (ms)')
        ax.set_ylabel('Time-to-Fetch (ms)')
        ax.set_title('Time-to-fetch for a latency of ' + latency + ' ms')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid()
        ax.legend()

        p_index += 1

    plt.suptitle(f"Time-to-Fetch for different trickling delays and topology {topology}")
    plt.tight_layout(h_pad=2, w_pad=4)
    # fig.tight_layout(rect=[0,0,.8,0.8])
    # plt.subplots_adjust(top=0.94)


def plot_time_to_fetch(latency, byTricklingDelay):
    p_index = 1
    x = []
    y = {}
    tc = {}

    fig = plt.figure(figsize=(10, 10))
    plt.xlabel('Trickling Delay (ms)')
    plt.ylabel('Time-to-Fetch (ms)')
    labels = []

    for f in byTricklingDelay:
        x.append(int(f))
        labels.append(int(f))

        y[f] = []
        tc[f] = []
        for i in byTricklingDelay[f]:
            if i["nodeType"] == "Leech":
                if i["meta"] == "time_to_fetch":
                    y[f].append(i["value"])
                if i["meta"] == "tcp_fetch":
                    tc[f].append(i["value"])

        avg = []
        for i in y:
            scaled_y = [i / 1e6 for i in y[i]]
            plt.scatter([int(i)] * len(y[i]), scaled_y, marker="+")
            if len(scaled_y) > 0:
                avg.append(sum(scaled_y) / len(scaled_y))
            else:
                avg.append(0)
        avg_tc = []
        for i in tc:
            scaled_tc = [i / 1e6 for i in tc[i]]
            plt.scatter([int(i)] * len(tc[i]), scaled_tc, marker="*")
            if len(scaled_tc) > 0:
                avg_tc.append(sum(scaled_tc) / len(scaled_tc))
            else:
                avg_tc.append(0)

    # print(y)
    plt.plot(x, avg, label="Protocol fetch")
    plt.plot(x, avg_tc, label="TCP fetch")

    plt.xticks(ticks=x, labels=labels)
    plt.grid()
    plt.legend()

    p_index += 1

    plt.title(f"Time-to-Fetch for different trickling delays with latency {latency}")
    # plt.tight_layout(h_pad=4, w_pad=4)
    # fig.tight_layout(rect=[0,0,.8,0.8])
    # plt.subplots_adjust(top=0.94)


def plot_tcp_latency(byLatency, byBandwidth, byFileSize):
    plt.figure()

    p1, p2 = len(byLatency), len(byBandwidth)
    pindex = 1
    x = []
    tc = {}
    for l in byLatency:

        for b in byBandwidth:
            ax = plt.subplot(p1, p2, pindex)
            ax.set_title("latency: " + l + " bandwidth: " + b)
            ax.set_xlabel('File Size (MB)')
            ax.set_ylabel('time_to_fetch (ms)')

            for f in byFileSize:

                x.append(int(f) / 1e6)

                tc[f] = []
                for i in byFileSize[f]:
                    if i["latencyMS"] == l and i["bandwidthMB"] == b and \
                            i["nodeType"] == "Leech":
                        if i["meta"] == "tcp_fetch":
                            tc[f].append(i["value"])

                avg_tc = []
                for i in tc:
                    scaled_tc = [i / 1e6 for i in tc[i]]
                    ax.scatter([int(i) / 1e6] * len(tc[i]), scaled_tc, marker="*")
                    avg_tc.append(sum(scaled_tc) / len(scaled_tc))

            # print(x, tc)
            ax.plot(x, avg_tc, label="TCP fetch")
            ax.legend()

            pindex += 1
            x = []
            tc = {}


def create_average_messages_dataframe(metrics, eaves_count):
    df = pd.DataFrame(columns=["Latency", "Trickling Delay", "File Size", "Type", "Eaves Count"])

    by_latency = process.groupBy(metrics, "latencyMS")
    by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
    for latency, latency_items in by_latency:
        by_filesize = process.groupBy(latency_items, "fileSize")
        by_filesize = sorted(by_filesize.items(), key=lambda x: int(x[0]))
        for filesize, filesize_items in by_filesize:
            by_trickling_delay = process.groupBy(filesize_items, "tricklingDelay")
            by_trickling_delay = sorted(by_trickling_delay.items(), key=lambda x: int(x[0]))

            for delay, value in by_trickling_delay:
                blks_sent = blks_rcvd = dup_blks_rcvd = msgs_rcvd = 0
                blks_sent_n = blks_rcvd_n = dup_blks_rcvd_n = msgs_rcvd_n = 0
                for i in value:
                    if i["meta"] == "blks_sent":
                        blks_sent += i["value"]
                        blks_sent_n += 1
                    if i["meta"] == "blks_rcvd":
                        blks_rcvd += i["value"]
                        blks_rcvd_n += 1
                    if i["meta"] == "dup_blks_rcvd":
                        dup_blks_rcvd += i["value"]
                        dup_blks_rcvd_n += 1
                    if i["meta"] == "msgs_rcvd":
                        msgs_rcvd += i["value"]
                        msgs_rcvd_n += 1

                df = df.append({"Latency": latency, "Trickling Delay": delay,
                                "File Size": filesize,
                                "Type": "Blocks Sent",
                                "value": blks_sent / blks_sent_n,
                                "Eaves Count": eaves_count}, ignore_index=True)
                df = df.append({"Latency": latency, "Trickling Delay": delay,
                                "File Size": filesize,
                                "Type": "Blocks Received",
                                "value": blks_rcvd / blks_rcvd_n,
                                "Eaves Count": eaves_count}, ignore_index=True)
                df = df.append({"Latency": latency, "Trickling Delay": delay,
                                "File Size": filesize,
                                "Type": "Duplicate Blocks Received",
                                "value": dup_blks_rcvd / dup_blks_rcvd_n,
                                "Eaves Count": eaves_count}, ignore_index=True)
                df = df.append({"Latency": latency, "Trickling Delay": delay,
                                "File Size": filesize,
                                "Type": "Messages Received",
                                "value": msgs_rcvd / msgs_rcvd_n,
                                "Eaves Count": eaves_count}, ignore_index=True)
    return df


def plot_grouped_stacks(filename, BGV, fig_size=(10, 8),
                        intra_group_spacing=0.1,
                        inter_group_spacing=10,
                        y_loc_for_group_name=-5,
                        y_loc_for_hstack_name=5,
                        fontcolor_hstacks='blue',
                        fontcolor_groups='black',
                        fontsize_hstacks=20,
                        fontsize_groups=30,
                        x_trim_hstack_label=0,
                        x_trim_group_label=0,
                        extra_space_on_top=20
                        ):
    figure_ = plt.figure(figsize=fig_size)
    size = figure_.get_size_inches()
    figure_.add_subplot(1, 1, 1)

    # sanity check for inputs; some trivial exception handlings
    if intra_group_spacing >= 100:
        print("Percentage for than 100 for variables intra_group_spacing, Aborting! ")
        return
    else:
        intra_group_spacing = intra_group_spacing * size[0] / 100  # converting percentanges to inches

    if inter_group_spacing >= 100:
        print("Percentage for than 100 for variables inter_group_spacing, Aborting! ")
        return
    else:
        inter_group_spacing = inter_group_spacing * size[0] / 100  # converting percentanges to inches

    if y_loc_for_group_name >= 100:
        print("Percentage for than 100 for variables inter_group_spacing, Aborting! ")
        return
    else:
        # the multiplier 90 is set empirically to roughly align the percentage value
        # <this is a quick fix solution, which needs to be improved later>
        y_loc_for_group_name = 90 * y_loc_for_group_name * size[1] / 100  # converting percentanges to inches

    if y_loc_for_hstack_name >= 100:
        print("Percentage for than 100 for variables inter_group_spacing, Aborting! ")
        return
    else:
        y_loc_for_hstack_name = 70 * y_loc_for_hstack_name * size[1] / 100  # converting percentanges to inches

    if x_trim_hstack_label >= 100:
        print("Percentage for than 100 for variables inter_group_spacing, Aborting! ")
        return
    else:
        x_trim_hstack_label = x_trim_hstack_label * size[0] / 100  # converting percentanges to inches

    if x_trim_group_label >= 100:
        print("Percentage for than 100 for variables inter_group_spacing, Aborting! ")
        return
    else:
        x_trim_group_label = x_trim_group_label * size[0] / 100  # converting percentanges to inches

    fileread_list = []

    with open(filename) as f:
        for row in f:
            r = row.strip().split(',')
            if len(r) != 4:
                print('4 items not found @ line ', c, ' of ', filename)
                return
            else:
                fileread_list.append(r)

    # inputs:
    bar_variable = BGV[0]
    group_variable = BGV[1]
    vertical_stacking_variable = BGV[2]

    first_line = fileread_list[0]
    for i in range(4):
        if first_line[i] == vertical_stacking_variable:
            header_num_Of_vertical_stacking = i
            break

    sorted_order_for_stacking = []
    for listed in fileread_list[1:]:  # skipping the first line
        sorted_order_for_stacking.append(listed[header_num_Of_vertical_stacking])
    sorted_order_for_stacking = list(set(sorted_order_for_stacking))
    list.sort(sorted_order_for_stacking)
    sorted_order_for_stacking_V = list(sorted_order_for_stacking)
    #####################

    first_line = fileread_list[0]
    for i in range(4):
        if first_line[i] == bar_variable:
            header_num_Of_bar_Variable = i
            break

    sorted_order_for_stacking = []
    for listed in fileread_list[1:]:  # skipping the first line
        sorted_order_for_stacking.append(listed[header_num_Of_bar_Variable])
    sorted_order_for_stacking = list(set(sorted_order_for_stacking))
    list.sort(sorted_order_for_stacking)
    sorted_order_for_stacking_H = list(sorted_order_for_stacking)
    ######################

    first_line = fileread_list[0]
    for i in range(4):
        if first_line[i] == group_variable:
            header_num_Of_bar_Variable = i
            break

    sorted_order_for_stacking = []
    for listed in fileread_list[1:]:  # skipping the first line
        sorted_order_for_stacking.append(listed[header_num_Of_bar_Variable])
    sorted_order_for_stacking = list(set(sorted_order_for_stacking))
    list.sort(sorted_order_for_stacking)
    sorted_order_for_stacking_G = list(sorted_order_for_stacking)
    #########################

    print(" Vertical/Horizontal/Groups  ")
    print(sorted_order_for_stacking_V, " : Vertical stacking labels")
    print(sorted_order_for_stacking_H, " : Horizontal stacking labels")
    print(sorted_order_for_stacking_G, " : Group names")

    # +1 because we need one space before and after as well
    each_group_width = (size[0] - (len(sorted_order_for_stacking_G) + 1) *
                        inter_group_spacing) / len(sorted_order_for_stacking_G)

    # -1 because we need n-1 spaces between bars if there are n bars in each group
    each_bar_width = (each_group_width - (len(sorted_order_for_stacking_H) - 1) *
                      intra_group_spacing) / len(sorted_order_for_stacking_H)

    # colormaps
    number_of_color_maps_needed = len(sorted_order_for_stacking_H)
    number_of_levels_in_each_map = len(sorted_order_for_stacking_V)
    c_map_vertical = {}

    for i in range(number_of_color_maps_needed):
        try:
            c_map_vertical[sorted_order_for_stacking_H[i]] = sequential_colors[i]
        except:
            print("Something went wrong with hardcoded colors!\n reverting to custom colors (linear in RGB) ")
            c_map_vertical[sorted_order_for_stacking_H[i]] = getColorMaps(N=number_of_levels_in_each_map, type='S')

    ##

    state_num = -1
    max_bar_height = 0
    for state in sorted_order_for_stacking_H:
        state_num += 1
        week_num = -1
        for week in ['Week 1', 'Week 2', 'Week 3']:
            week_num += 1

            a = [0] * len(sorted_order_for_stacking_V)
            for i in range(len(sorted_order_for_stacking_V)):

                for line_num in range(1, len(fileread_list)):  # skipping the first line
                    listed = fileread_list[line_num]

                    if listed[1] == state and listed[0] == week and listed[2] == sorted_order_for_stacking_V[i]:
                        a[i] = (float(listed[3]))

            # get cumulative values
            cum_val = [a[0]]
            for j in range(1, len(a)):
                cum_val.append(cum_val[j - 1] + a[j])
            max_bar_height = max([max_bar_height, max(cum_val)])

            plt.text(x=(week_num) * (each_group_width + inter_group_spacing) - x_trim_group_label
                     , y=y_loc_for_group_name, s=sorted_order_for_stacking_G[week_num], fontsize=fontsize_groups,
                     color=fontcolor_groups)

            # state labels need to be printed just once for each week, hence putting them outside the loop
            plt.text(x=week_num * (each_group_width + inter_group_spacing) + (state_num) * (
                    each_bar_width + intra_group_spacing) - x_trim_hstack_label
                     , y=y_loc_for_hstack_name, s=sorted_order_for_stacking_H[state_num], fontsize=fontsize_hstacks,
                     color=fontcolor_hstacks)

            if week_num == 1:
                # label only in the first week

                for i in range(len(sorted_order_for_stacking_V) - 1, -1, -1):
                    # trick to make them all visible: Plot in descending order of their height!! :)
                    plt.bar(week_num * (each_group_width + inter_group_spacing) +
                            state_num * (each_bar_width + intra_group_spacing),
                            height=cum_val[i],
                            width=each_bar_width,
                            color=c_map_vertical[state][i],
                            label=state + "_" + sorted_order_for_stacking_V[i])
            else:
                # no label after the first week, (as it is just repetition)
                for i in range(len(sorted_order_for_stacking_V) - 1, -1, -1):
                    plt.bar(week_num * (each_group_width + inter_group_spacing) +
                            state_num * (each_bar_width + intra_group_spacing),
                            height=cum_val[i],
                            width=each_bar_width,
                            color=c_map_vertical[state][i])

    plt.ylim(0, max_bar_height * (1 + extra_space_on_top / 100))
    plt.tight_layout()
    plt.xticks([], [])
    plt.legend(ncol=len(sorted_order_for_stacking_H))
    return figure_


def plot_messages_overall(df):
    df.sort_values(by=['Eaves Count'], inplace=True)

    # replace eavesdropper 0 with 'baseline' for better readability
    df['Eaves Count'] = df['Eaves Count'].replace('0', 'baseline')

    df.to_csv('message_metrics.csv', index=False)

    f = plot_grouped_stacks('message_metrics.csv', BGV=['Eaves Count', 'Trickling Delay', 'Type'],
                            extra_space_on_top=30)

    # g.set(xlabel='Trickling delay (ms)', ylabel='Count')
    # g.add_legend()


def plot_messages(topology, by_latency):
    plt.figure(figsize=(15, 15))

    # labels = []
    axes = []
    p1, p2 = len(by_latency), 1
    p_index = 1
    # sort latency ascending
    by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
    for latency, latency_items in by_latency:
        by_trickling_delay = process.groupBy(latency_items, "tricklingDelay")
        by_trickling_delay = sorted(by_trickling_delay.items(), key=lambda x: int(x[0]))

        ax = plt.subplot(p1, p2, p_index, sharey=axes[0] if len(axes) > 0 else None)
        axes.append(ax)
        labels = []
        arr_blks_sent = []
        arr_blks_rcvd = []
        arr_dup_blks_rcvd = []
        arr_msgs_rcvd = []
        for delay, value in by_trickling_delay:
            labels.append(int(delay))
            x = np.arange(len(labels))  # the label locations
            blks_sent = blks_rcvd = dup_blks_rcvd = msgs_rcvd = 0
            blks_sent_n = blks_rcvd_n = dup_blks_rcvd_n = msgs_rcvd_n = 0
            width = 1 / 4

            for i in value:
                if i["meta"] == "blks_sent":
                    blks_sent += i["value"]
                    blks_sent_n += 1
                if i["meta"] == "blks_rcvd":
                    blks_rcvd += i["value"]
                    blks_rcvd_n += 1
                if i["meta"] == "dup_blks_rcvd":
                    dup_blks_rcvd += i["value"]
                    dup_blks_rcvd_n += 1
                if i["meta"] == "msgs_rcvd":
                    msgs_rcvd += i["value"]
                    msgs_rcvd_n += 1

            # Computing averages
            # Remove the division if you want to see total values
            if blks_rcvd_n > 0:
                arr_blks_rcvd.append(round(blks_rcvd / blks_rcvd_n, 1))
            if blks_sent_n > 0:
                arr_blks_sent.append(round(blks_sent / blks_sent_n, 1))
            if dup_blks_rcvd_n > 0:
                arr_dup_blks_rcvd.append(round(dup_blks_rcvd / dup_blks_rcvd_n, 1))
            if msgs_rcvd_n > 0:
                arr_msgs_rcvd.append(round(msgs_rcvd / msgs_rcvd_n, 1))

        bar1 = ax.bar(x - (3 / 2) * width, arr_msgs_rcvd, width, label="Messages Received")
        bar2 = ax.bar(x - width / 2, arr_blks_rcvd, width, label="Blocks Received")
        bar3 = ax.bar(x + width / 2, arr_blks_sent, width, label="Blocks Sent")
        bar4 = ax.bar(x + (3 / 2) * width, arr_dup_blks_rcvd, width, label="Duplicate blocks")

        autolabel(ax, bar1)
        autolabel(ax, bar2)
        autolabel(ax, bar3)
        autolabel(ax, bar4)

        ax.set_title('Average number of messages exchanged for latency ' + latency + 'ms')
        ax.set(xticks=x, xticklabels=labels, xlabel="Trickling Delay (ms)", ylabel="Number of Messages")
        ax.legend()
        ax.grid()
        p_index += 1

    plt.suptitle("Average number of messages exchanged for topology " + topology, fontsize=16)
    plt.tight_layout()


from matplotlib.backends.backend_pdf import PdfPages

if __name__ == "__main__":
    args = parse_args()

    # Set this to something else
    results_dir = dir_path + '/../../experiments' + '/results'
    target_dir = results_dir
    if args.dir:
        results_dir = args.dir

    agg, testcases = aggregate_metrics(results_dir)
    # byLatency = groupBy(agg, "latencyMS")
    # byNodeType = groupBy(agg, "nodeType")
    # byFileSize = groupBy(agg, "fileSize")
    # byBandwidth = groupBy(agg, "bandwidthMB")
    byTopology = groupBy(agg, "topology")
    # byConnectionRate = groupBy(agg, "maxConnectionRate")

    for topology, topology_metrics in byTopology.items():
        with PdfPages(target_dir + "/" + f"time-to-fetch-{topology}.pdf") as export_pdf:
            plot_time_to_fetch_for_all_eavescounts(topology, topology_metrics, export_pdf)

    # plot_time_to_fetch(byLatency, byBandwidth)
    # plot_messages(byFileSize, byTopology)
    # plot_througput(byLatency, byBandwidth, byFileSize, byTopology, testcases)
    # plot_tcp_latency(byLatency, byBandwidth, byFileSize)
    # plot_want_messages(byFileSize, byTopology)
    #
    # output_latency(byFileSize, byTopology)
    # output_avg_data(byFileSize, byTopology, "Seed")
    # output_avg_data(byFileSize, byTopology, "Leech")

    plt.show()
