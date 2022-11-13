import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

import process


def create_average_messages_dataframe_compact(metrics, eaves_count):
    df = pd.DataFrame(columns=["Latency", "Trickling Delay", "File Size", "Type", "Eaves Count", "Experiment Type"])

    by_experiment_type = process.groupBy(metrics, "exType")
    for ex_type, ex_type_items in by_experiment_type.items():
        by_latency = process.groupBy(ex_type_items, "latencyMS")
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
                                    "Experiment Type": ex_type,
                                    "Type": "Blocks Sent",
                                    "value": blks_sent / blks_sent_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency, "Trickling Delay": delay,
                                    "File Size": filesize,
                                    "Experiment Type": ex_type,
                                    "Type": "Blocks Received",
                                    "value": blks_rcvd / blks_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency, "Trickling Delay": delay,
                                    "File Size": filesize,
                                    "Experiment Type": ex_type,
                                    "Type": "Duplicate Blocks Received",
                                    "value": dup_blks_rcvd / dup_blks_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency, "Trickling Delay": delay,
                                    "File Size": filesize,
                                    "Experiment Type": ex_type,
                                    "Type": "Messages Received",
                                    "value": msgs_rcvd / msgs_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
    return df


def create_average_messages_dataframe_long(metrics, eaves_count):
    df = pd.DataFrame(
        columns=["Latency", "Trickling Delay", "File Size", "Eaves Count", "Experiment Type", "Blocks Sent",
                 "Blocks Received", "Duplicate Blocks Received", "Messages Received"])

    by_experiment_type = process.groupBy(metrics, "exType")
    for ex_type, ex_type_items in by_experiment_type.items():
        by_latency = process.groupBy(ex_type_items, "latencyMS")
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
                                    "Experiment Type": ex_type,
                                    "value": blks_sent / blks_sent_n,
                                    "Eaves Count": eaves_count,
                                    "Blocks Sent": blks_sent / blks_sent_n,
                                    "Blocks Received": blks_rcvd / blks_rcvd_n,
                                    "Duplicate Blocks Received": dup_blks_rcvd / dup_blks_rcvd_n,
                                    "Messages Received": msgs_rcvd / msgs_rcvd_n}, ignore_index=True)
    return df


def plot_messages_overall(dataframe_long):
    # rename variable to make it shorter
    df = dataframe_long
    df.sort_values(by=['Eaves Count'], inplace=True)

    plt.figure(figsize=(15, 15))

    # labels = []
    axes = []
    unique_latencies = dataframe_long["Latency"].unique()
    unique_file_sizes = dataframe_long["File Size"].unique()
    unique_experiment_types = dataframe_long["Experiment Type"].unique()

    p_index = 1

    for latency in unique_latencies:
        for filesize in unique_file_sizes:
            if len(axes) == 0:
                ax = plt.subplot(len(unique_latencies), len(unique_file_sizes), p_index)
            else:
                ax = plt.subplot(len(unique_latencies), len(unique_file_sizes), p_index, sharey=axes[0])
            for ex_type in unique_experiment_types:
                # TODO make them overlap
                # TODO only count runs where the fetch did not fail

                data = df[
                    (df["Latency"] == latency) & (df["File Size"] == filesize) & (df["Experiment Type"] == ex_type)]

                if len(data) == 0:
                    continue

                labels = data['Trickling Delay'].unique()
                x = np.arange(len(labels))  # the label locations

                width = 1 / 4
                bar1 = ax.bar(x - (3 / 2) * width, data['Messages Received'], width, label="Messages Received")
                bar2 = ax.bar(x - width / 2, data['Blocks Received'], width, label="Blocks Received")
                bar3 = ax.bar(x + width / 2, data['Blocks Sent'], width, label="Blocks Sent")
                bar4 = ax.bar(x + (3 / 2) * width, data['Duplicate Blocks Received'], width,
                              label="Duplicate Blocks Received")

                # autolabel(ax, bar1)
                # autolabel(ax, bar2)
                # autolabel(ax, bar3)
                # autolabel(ax, bar4)

                ax.set_title(f'Latency: {latency} | File Size: {filesize}')
                ax.set(xticks=x, xticklabels=labels, xlabel="Trickling Delay (ms)", ylabel="Number of Messages")
                ax.legend()
                p_index += 1
                axes.append(ax)

    plt.tight_layout()


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

        process.autolabel(ax, bar1)
        process.autolabel(ax, bar2)
        process.autolabel(ax, bar3)
        process.autolabel(ax, bar4)

        ax.set_title('Average number of messages exchanged for latency ' + latency + 'ms')
        ax.set(xticks=x, xticklabels=labels, xlabel="Trickling Delay (ms)", ylabel="Number of Messages")
        ax.legend()
        ax.grid()
        p_index += 1

    plt.suptitle("Average number of messages exchanged for topology " + topology, fontsize=16)
    plt.tight_layout()
