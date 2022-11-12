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

    by_latency = process.groupBy(metrics, "latencyMS")
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
                                     'Eaves Count': [eaves_count] * len(scaled_y)})
                overall_frame = pd.concat([overall_frame, test])

            averages.append(
                {'x': x, 'avg_normal': avg, 'avg_tc': avg_tc, 'eaves_count': eaves_count, 'latency': latency,
                 'filesize': filesize})

    return overall_frame, averages


def get_color_for_index(index, palette):
    return palette[index % len(palette)]


# Parameters
# ----------
# df : dataframe consisting of the data to be plotted
# combined_averages : list of dictionaries containing the average values for each eavesdropper count
def plot_time_to_fetch_per_topology(df, combined_averages):
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
    df = pd.DataFrame(columns=["Latency", "Trickling Delay", "File Size", "Blocks Sent", "Blocks Received",
                               "Duplicate Blocks Received", "Messages Received", "Eaves Count"])

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

                df = df.append({"Latency": latency, "Trickling Delay": delay, "File Size": filesize,
                                "Blocks Sent": blks_sent / blks_sent_n,
                                "Blocks Received": blks_rcvd / blks_rcvd_n,
                                "Duplicate Blocks Received": dup_blks_rcvd / dup_blks_rcvd_n,
                                "Messages Received": msgs_rcvd / msgs_rcvd_n,
                                "Eaves Count": eaves_count}, ignore_index=True)

    return df


def plot_messages_overall(dataframe):
    # TODO

    sns.histplot(penguins, x="flipper_length_mm", hue="species", element="step")

    pass


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
            plot_time_to_fetch_per_topology(topology, topology_metrics, export_pdf)

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
