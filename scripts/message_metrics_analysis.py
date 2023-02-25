import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

import process


def create_average_messages_dataframe_compact(metrics, eaves_count):
    """
    Create a dataframe containing the average number of messages received, and (duplicate) blocks sent and received
    :param metrics: The metrics to analyse
    :param eaves_count: The number of eavesdroppers that were used in the experiment
    :return: the dataframe containing the metrics
    """
    df = pd.DataFrame(columns=["Latency", "Trickling Delay", "File Size", "Type", "Eaves Count", "Experiment Type"])

    by_experiment_type = process.group_by(metrics, "exType")
    for ex_type, ex_type_items in by_experiment_type.items():
        by_latency = process.group_by(ex_type_items, "latencyMS")
        by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
        for latency, latency_items in by_latency:
            by_filesize = process.group_by(latency_items, "fileSize")
            by_filesize = sorted(by_filesize.items(), key=lambda x: int(x[0]))
            for filesize, filesize_items in by_filesize:
                by_trickling_delay = process.group_by(filesize_items, "tricklingDelay")
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

                    df = df.append({"Latency": latency + ' ms',
                                    "Trickling Delay": delay,
                                    "File Size": filesize + ' B',
                                    "Experiment Type": ex_type,
                                    "Type": "Blocks Sent",
                                    "value": blks_sent / blks_sent_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency + ' ms',
                                    "Trickling Delay": delay,
                                    "File Size": filesize + ' B',
                                    "Experiment Type": ex_type,
                                    "Type": "Blocks Received",
                                    "value": blks_rcvd / blks_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency + ' ms',
                                    "Trickling Delay": delay,
                                    "File Size": filesize + ' B',
                                    "Experiment Type": ex_type,
                                    "Type": "Duplicate Blocks Received",
                                    "value": dup_blks_rcvd / dup_blks_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
                    df = df.append({"Latency": latency + ' ms',
                                    "Trickling Delay": delay,
                                    "File Size": filesize + ' B',
                                    "Experiment Type": ex_type,
                                    "Type": "Messages Received",
                                    "value": msgs_rcvd / msgs_rcvd_n,
                                    "Eaves Count": eaves_count}, ignore_index=True)
    return df


def plot_messages_for_0_trickling(dataframe_compact):
    """
    Plots the average number of messages sent, received, and duplicate blocks received comparing the baseline to trickle
    forwarding with 0 delay
    :param dataframe_compact: The dataframe containing the metrics
    """
    # rename variable to make it shorter
    df = dataframe_compact
    df.sort_values(by=['Eaves Count'], inplace=True)

    # Replace the experiment type with a more readable name
    df['Experiment Type'] = df['Experiment Type'].replace({'baseline': 'Baseline', 'trickle': 'Forwarding'})

    plt.figure(figsize=(15, 15))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})
    # We only want to plot the 0 trickling delay
    target = df[df["Trickling Delay"] == '0']

    order = ['Forwarding', 'Baseline']
    col_order = ['512 B', '153600 B', '1048576 B']
    row_order = ['50 ms', '100 ms', '150 ms']
    hue_order = ["Messages Received", "Blocks Sent", "Blocks Received", "Duplicate Blocks Received"]

    g = sns.catplot(data=target, x="Experiment Type", y="value", hue="Type", col="File Size", row="Latency", kind="bar",
                    order=order, hue_order=hue_order, col_order=col_order, row_order=row_order,
                    margin_titles=True)
    g.set_axis_labels("Experiment Type", "Average Number of Type")
    sns.despine(offset=10, trim=False)

    # Draw height of bars on top of the bars
    flatiter = g.axes.flat
    for ax in flatiter:
        for i in ax.containers:
            ax.bar_label(i, fmt="%.2f", label_type='edge')
