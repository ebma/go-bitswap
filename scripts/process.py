import argparse
import json
import math
import os
import sys

import numpy as np
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


# def groupby(arr, key):
#     res = {}
#     for l in arr:
#         if !l[]
#         if len(res[""])
def process_result_line(line, experiment_id):
    line = json.loads(line)
    name = line["name"].split('/')
    value = (line["measures"])["value"]
    item = {}
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    item["value"] = value
    item['experiment'] = experiment_id
    return item


def aggregate_results(results_dir):
    res = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "results.out":
                # print (filepath)
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                resultFile = open(filepath, 'r')
                for l in resultFile.readlines():
                    res.append(process_result_line(l, experiment_id))
    return res, len(os.listdir(results_dir))


def groupBy(agg, metric):
    res = {}
    for item in agg:
        if not item[metric] in res:
            res[item[metric]] = []
        res[item[metric]].append(item)
    return res


def plot_latency_no_comparision(byLatency, byBandwidth, byFileSize):
    plt.figure()

    p1, p2 = len(byLatency), len(byBandwidth)
    pindex = 1
    x = []
    y = {}
    tc = {}
    for l in byLatency:

        for b in byBandwidth:
            ax = plt.subplot(p1, p2, pindex)
            ax.set_title("latency: " + l + " bandwidth: " + b)
            ax.set_xlabel('File Size (MB)')
            ax.set_ylabel('time_to_fetch (ms)')

            for f in byFileSize:

                x.append(int(f) / 1e6)

                y[f] = []
                for i in byFileSize[f]:
                    if i["latencyMS"] == l and i["bandwidthMB"] == b and \
                            i["nodeType"] == "Leech":
                        if i["meta"] == "time_to_fetch":
                            y[f].append(i["value"])

                avg = []
                for i in y:
                    scaled_y = [i / 1e6 for i in y[i]]
                    ax.scatter([int(i) / 1e6] * len(y[i]), scaled_y, marker="+")
                    avg.append(sum(scaled_y) / len(scaled_y))

            # print(y)
            ax.plot(x, avg, label="Protocol fetch")

            ax.legend()

            pindex += 1
            x = []
            y = {}
            tc = {}


def plot_time_to_fetch_grouped_with_filesize(topology, by_latency, filter_outliers=True):
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

        plt.suptitle(f"Time-to-Fetch for different trickling delays, file sizes and topology {topology}")
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


def autolabel(ax, rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')


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


def plot_want_messages(byFileSize, byTopology):
    # plt.figure()

    for t in byTopology:
        # t_aux = t.replace("(","").replace(")","").split(",")
        # instances = int(t_aux[0]) + int(t_aux[1])

        labels = []
        # arr_wants_avg = []
        arr_wants_max = []
        arr_wants_total = []
        arr_wants_avg_single = []
        arr_want_haves = []
        arr_want_blocks = []

        for f in byFileSize:
            labels.append(int(f) / 1e6)
            x = np.arange(len(labels))  # the label locations
            wants = want_haves = want_blocks = 0
            wants_n = want_max = 0
            width = 1 / 4

            for i in byFileSize[f]:
                if i["topology"] == t:
                    if i["meta"] == "wants_rcvd":
                        wants += i["value"]
                        wants_n += 1
                        if want_max < i["value"]:
                            want_max = i["value"]
                    if i["meta"] == "want_blocks_rcvd":
                        want_blocks += i["value"]
                    if i["meta"] == "want_haves_rcvd":
                        want_haves += i["value"]

            # Computing averages
            # Remove the division if you want to see total values 
            # arr_wants_avg.append(round(wants/instances/1000,1))
            # arr_want_haves.append(round(want_haves/wants_n,1)) # TODO fix division by zero here
            # arr_want_blocks.append(round(want_blocks/wants_n,1))
            # arr_wants_avg_single.append(round(wants/wants_n,1))
            arr_wants_max.append(want_max)
            arr_wants_total.append(wants / 1000)

            wants = 0
            wants_n = want_max = 0

        fig, ax = plt.subplots()
        bar1a = ax.bar(x - (3 / 2) * width, arr_want_haves, width, label="Average want-haves")
        bar1b = ax.bar(x - (3 / 2) * width, arr_want_blocks, width, label="Average want-blocks")
        bar2 = ax.bar(x - width / 2, arr_wants_avg_single, width, label="Average wants per node in single file")
        bar3 = ax.bar(x + width / 2, arr_wants_max, width, label="Max wants received by node in single file")
        bar4 = ax.bar(x + (3 / 2) * width, arr_wants_total, width,
                      label="Total want messages exchanged in test (KMessages)")

        autolabel(ax, bar1a)
        autolabel(ax, bar1b)
        autolabel(ax, bar2)
        autolabel(ax, bar3)
        autolabel(ax, bar4)

        ax.set_ylabel('Number of messages')
        ax.set_title('Average number of WANTs exchanged ' + t)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        fig.tight_layout()


def plot_bw_overhead(byFileSize, byTopology):
    # plt.figure()

    for t in byTopology:
        labels = []
        arr_control_rcvd = []
        arr_block_data_rcvd = []
        arr_dup_data_rcvd = []
        arr_overhead = []
        for f in byFileSize:
            # TODO: Considering a 5.5% overhead of TPC
            leechCount = t.replace("(", "").replace(")", "").split("-")[1]
            print("Leech count: " + leechCount)
            TCP_BASELINE = int(leechCount) * 1.055 * int(f)
            print("TCP baseline: " + str(TCP_BASELINE))
            labels.append(int(f) / 1e6)
            x = np.arange(len(labels))  # the label locations
            data_rcvd = block_data_rcvd = dup_data_rcvd = overhead = 0
            data_rcvd_n = block_data_rcvd_n = dup_data_rcvd_n = overhead_n = 0
            width = 1 / 4

            for i in byFileSize[f]:
                # We are only interested in leechers so we don't duplicate measurements.
                if i["nodeType"] == "Leech" and i["topology"] == t:
                    if i["meta"] == "data_rcvd":
                        data_rcvd += i["value"]
                        data_rcvd_n += 1
                        overhead = (data_rcvd - TCP_BASELINE) * 100 / TCP_BASELINE
                        overhead_n += 1
                    if i["meta"] == "block_data_rcvd":
                        block_data_rcvd += i["value"]
                        block_data_rcvd_n += 1
                    if i["meta"] == "dup_data_rcvd":
                        dup_data_rcvd += i["value"]
                        dup_data_rcvd_n += 1

            control_rcvd = data_rcvd - block_data_rcvd
            # Computing averages
            # Remove the division if you want to see total values 
            arr_control_rcvd.append(round(control_rcvd / data_rcvd_n / 1e6, 3))
            if block_data_rcvd_n != 0:
                arr_block_data_rcvd.append(round(block_data_rcvd / block_data_rcvd_n / 1e6, 3))
            else:
                arr_block_data_rcvd.append(0)
            arr_dup_data_rcvd.append(round(dup_data_rcvd / dup_data_rcvd_n / 1e6, 3))
            arr_overhead.append(round(overhead / overhead_n, 3))
            control_rcvd = data_rcvd = block_data_rcvd = dup_data_rcvd = overhead = 0
            data_rcvd_n = block_data_rcvd_n = dup_data_rcvd_n = overhead_n = 0

        fig, ax = plt.subplots()
        bar1 = ax.bar(x - (3 / 2) * width, arr_control_rcvd, width, label="Control data received (MB)")
        bar2 = ax.bar(x - width / 2, arr_block_data_rcvd, width, label="Total data received from blocks (MB)")
        bar3 = ax.bar(x + width / 2, arr_dup_data_rcvd, width, label="Total data received from duplicates (MB)")
        bar4 = ax.bar(x + (3 / 2) * width, arr_overhead, width, label="Bandwidth overhead (%)")

        autolabel(ax, bar1)
        autolabel(ax, bar2)
        autolabel(ax, bar3)
        autolabel(ax, bar4)

        ax.set_ylabel('Number of messages')
        # ax.set_ylabel('File Size (MB)') 
        ax.set_title('Data received ' + t)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        fig.tight_layout()


def output_avg_stream_data_bitswap(byFileSize, byTopology):
    for t in byTopology:
        labels = []
        arr_data_stream_sent = []

        for f in byFileSize:
            labels.append(int(f) / 1e6)

            stream_data_sent = 0
            stream_data_sent_n = 0

            for i in byFileSize[f]:
                # We are only interested in leechers so we don't duplicate measurements.
                if i["nodeType"] == "Seed" and i["topology"] == t:
                    if i["meta"] == "stream_data_sent":
                        stream_data_sent += i["value"]
                        stream_data_sent_n += 1

            # Computing averages
            # Remove the division if you want to see total values 
            arr_data_stream_sent.append(round(stream_data_sent / stream_data_sent_n / 1e6, 3))
            stream_data_sent = 0
            stream_data_sent_n = 0

        print("=== Stream Data Sent ===")
        print("[*] Topology: ", t)
        i = 0
        for x in labels:
            print("Filesize: %s MB -- Avg. Stream Data Sent Seeders: %s MB" % (x, arr_data_stream_sent[i]))
            i += 1


def output_latency(byFileSize, byTopology):
    for t in byTopology:
        labels = []
        arr_time_to_fetch = []

        for f in byFileSize:
            labels.append(int(f) / 1e6)

            time_to_fetch = 0
            time_to_fetch_n = 0

            for i in byFileSize[f]:
                # We are only interested in leechers so we don't duplicate measurements.
                if i["nodeType"] == "Leech" and i["topology"] == t:
                    if i["meta"] == "time_to_fetch":
                        time_to_fetch += i["value"]
                        time_to_fetch_n += 1

            # Computing averages
            # Remove the division if you want to see total values 
            arr_time_to_fetch.append(round(time_to_fetch / 1e6, 3))

            time_to_fetch = 0
            time_to_fetch_n = 0

        print("=== Time to fetch ====")
        print("[*] Topology: ", t)
        i = 0
        for x in labels:
            print("[*]Filesize: %s MB" % x)
            print("Avg. Time to Fetch: %s ms" % (arr_time_to_fetch[i]))
            i += 1


def output_avg_data(byFileSize, byTopology, nodeType):
    for t in byTopology:
        labels = []
        arr_total_data_in = []
        arr_total_data_out = []
        arr_total_rate_in = []
        arr_total_rate_out = []

        for f in byFileSize:
            labels.append(int(f) / 1e6)

            total_data_in = total_data_out = total_rate_in = total_rate_out = 0
            total_data_in_n = total_data_out_n = total_rate_in_n = total_rate_out_n = 0

            for i in byFileSize[f]:
                # We are only interested in leechers so we don't duplicate measurements.
                if i["nodeType"] == nodeType and i["topology"] == t:
                    if i["meta"] == "total_in":
                        total_data_in += i["value"]
                        total_data_in_n += 1
                    elif i["meta"] == "total_out":
                        total_data_out += i["value"]
                        total_data_out_n += 1
                    elif i["meta"] == "rate_in":
                        total_rate_in += i["value"]
                        total_rate_in_n += 1
                    elif i["meta"] == "rate_out":
                        total_rate_out += i["value"]
                        total_rate_out_n += 1

            # Computing averages
            # Remove the division if you want to see total values 
            arr_total_data_in.append(round(total_data_in / total_data_in_n / 1e6, 3))
            arr_total_data_out.append(round(total_data_out / total_data_out_n / 1e6, 3))
            arr_total_rate_in.append(round(total_rate_in / total_rate_in_n / 1e6, 3))
            arr_total_rate_out.append(round(total_rate_out / total_rate_out_n / 1e6, 3))

            total_data_in = total_data_out = total_rate_in = total_rate_out = 0
            total_data_in_n = total_data_out_n = total_rate_in_n = total_rate_out_n = 0

        print("=== Data Exchanges for %s ===" % nodeType)
        print("[*] Topology: ", t)
        i = 0
        for x in labels:
            print("[*]Filesize: %s MB" % x)
            print("Avg. Data In: %s MB" % (arr_total_data_in[i]))
            print("Avg. Data Out: %s MB" % (arr_total_data_out[i]))
            print("Avg. Rate In: %s MBps" % (arr_total_rate_in[i]))
            print("Avg. Rate Out: %s MBps" % (arr_total_rate_out[i]))
            i += 1


def plot_througput(byLatency, byBandwidth, byFileSize, byTopology, testcases):
    plt.figure()

    p1, p2 = 2, math.ceil(testcases / 2)
    pindex = 1
    x = []
    y = {}
    toPlot = False

    for t in byTopology:
        for l in byLatency:

            for b in byBandwidth:
                ax = plt.subplot(p1, p2, pindex)
                ax.set_title("Average Throughput - latency: " + l + "ms bandwidth: " + b + "MB topology: " + t)
                ax.set_xlabel('File Size (MB)')
                ax.set_ylabel('throughput (Mbps)')

                for f in byFileSize:
                    time_to_fetch = block_data_rcvd = dup_data_rcvd = 0
                    time_to_fetch_n = block_data_rcvd_n = dup_data_rcvd_n = 0
                    x.append(int(f) / 1e6)

                    y[f] = []
                    for i in byFileSize[f]:
                        if i["latencyMS"] == l and i["bandwidthMB"] == b and \
                                i["topology"] == t and i["nodeType"] == "Leech":
                            if i["meta"] == "time_to_fetch":
                                time_to_fetch += i["value"] / 1e6  # Get in ms
                                time_to_fetch_n += 1
                            if i["meta"] == "block_data_rcvd":
                                block_data_rcvd += i["value"]
                                block_data_rcvd_n += 1
                            if i["meta"] == "dup_data_rcvd":
                                dup_data_rcvd += i["value"]
                                dup_data_rcvd_n += 1

                    if time_to_fetch_n != 0:
                        avg_time_to_fetch = time_to_fetch / time_to_fetch_n / 1e3  # Use it in s
                        avg_data = ((block_data_rcvd / block_data_rcvd_n) - (
                                dup_data_rcvd / dup_data_rcvd_n)) / 1e6  # IN MB
                        y[f].append(avg_data / avg_time_to_fetch)

                        time_to_fetch = block_data_rcvd = dup_data_rcvd = 0
                        time_to_fetch_n = block_data_rcvd_n = dup_data_rcvd_n = 0
                        toPlot = True

                avg = []
                if toPlot:
                    for i in y:
                        ax.scatter([int(i) / 1e6] * len(y[i]), y[i], marker="+")
                        avg.append(sum(y[i]) / len(y[i]))

                    ax.plot(x, avg)
                    pindex += 1
                    toPlot = False

                x = []
                y = {}


if __name__ == "__main__":
    args = parse_args()

    results_dir = dir_path + '/results'
    if args.dir:
        results_dir = args.dir

    agg, testcases = aggregate_results(results_dir)
    byLatency = groupBy(agg, "latencyMS")
    byNodeType = groupBy(agg, "nodeType")
    byFileSize = groupBy(agg, "fileSize")
    byBandwidth = groupBy(agg, "bandwidthMB")
    byTopology = groupBy(agg, "topology")
    byConnectionRate = groupBy(agg, "maxConnectionRate")

    if args.plots is None and args.outputs is None:
        print("[!!] No plots or outputs provided...")
        sys.exit()

    if args.plots is not None:
        if "latency" in args.plots:
            plot_time_to_fetch(byLatency, byBandwidth, byFileSize)
        if "messages" in args.plots:
            plot_messages(byFileSize, byTopology)
        if "overhead" in args.plots:
            plot_bw_overhead(byFileSize, byTopology)
        if "throughput" in args.plots:
            plot_througput(byLatency, byBandwidth, byFileSize, byTopology, testcases)
        if "tcp" in args.plots:
            plot_tcp_latency(byLatency, byBandwidth, byFileSize)
        if "wants" in args.plots:
            plot_want_messages(byFileSize, byTopology)

    if args.outputs is not None:
        if "bitswap-data" in args.outputs:
            output_avg_stream_data_bitswap(byFileSize, byTopology)
        if "latency" in args.outputs:
            output_latency(byFileSize, byTopology)
        if "data" in args.outputs:
            output_avg_data(byFileSize, byTopology, "Seed")
            output_avg_data(byFileSize, byTopology, "Leech")

    plt.show()
