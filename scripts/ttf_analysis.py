import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

import process


def create_ttf_dataframe(metrics, eaves_count, filter_outliers=True):
    """
    Create a dataframe with the time-to-fetch values for each experiment type
    :param metrics: the metrics to analyze
    :param eaves_count: the number of eavesdroppers
    :param filter_outliers: whether to filter out outliers
    :return: the dataframe with the time-to-fetch values
    """
    outlier_threshold = 2

    overall_frame = pd.DataFrame(columns=['x', 'y', 'tc'])
    averages = pd.DataFrame(columns=['x', 'avg_normal', 'avg_tc', 'latency', 'filesize'])

    by_ex_type = process.group_by(metrics, 'exType')
    for ex_type, ex_type_items in by_ex_type.items():
        by_latency = process.group_by(ex_type_items, "latencyMS")
        by_latency = sorted(by_latency.items(), key=lambda x: int(x[0]))
        for latency, latency_items in by_latency:
            by_filesize = process.group_by(latency_items, "fileSize")
            by_filesize = sorted(by_filesize.items(), key=lambda x: int(x[0]))
            for filesize, filesize_items in by_filesize:
                by_trickling_delay = process.group_by(filesize_items, "tricklingDelay")
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
                                         'File Size': [filesize + ' B'] * len(scaled_y),
                                         'Experiment Type | Latency': [ex_type + ' | ' + latency + ' ms'] * len(
                                             scaled_y),
                                         })
                    overall_frame = pd.concat([overall_frame, test])


                average = pd.DataFrame({'x': x,
                                        'avg_normal': avg, 'avg_tc': avg_tc,
                                        'eaves_count': eaves_count, 'latency': latency, 'filesize': filesize})
                averages = pd.concat([averages, average])

    return overall_frame, averages


def plot_time_to_fetch_per_extype(df):
    """
    Plots the time-to-fetch values for each experiment type
    :param df: the dataframe with the time-to-fetch values
    """
    plt.figure(figsize=(10, 10))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})
    col_order = ['512 B', '153600 B', '1048576 B']
    hue_order = \
        ["baseline | 50 ms", "baseline | 100 ms", "baseline | 150 ms",
         "trickle | 50 ms", "trickle | 100 ms", "trickle | 150 ms"]

    # set log ticks for y axis
    ticks = [400, 800, 1600, 3200, 6400, 12800, 25600]
    labels = [str(i) for i in ticks]
    g = sns.catplot(data=df, x="x", y="y", hue="Experiment Type | Latency",
                    kind="strip", dodge=True, s=3, height=4,
                    col="File Size", col_order=col_order,
                    hue_order=hue_order).set(yscale="log")
    g.set(yticks=ticks, yticklabels=labels)
    g.set(xlabel='Trickling delay (ms)', ylabel='Time to Fetch (ms)')

    sns.despine(offset=10, trim=False)
