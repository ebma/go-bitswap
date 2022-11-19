import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

import process


def create_ttf_dataframe(metrics, eaves_count, filter_outliers=True):
    outlier_threshold = 2

    overall_frame = pd.DataFrame(columns=['x', 'y', 'tc'])
    averages = list()

    by_ex_type = process.groupBy(metrics, 'exType')
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
    col_order = ['512 bytes', '153600 bytes', '1048576 bytes']
    row_order = ["50 ms", "100 ms", "150 ms"]
    g = sns.FacetGrid(df, hue='Experiment Type', col="File Size", row="Latency",
                      palette=palette,
                      col_order=col_order,
                      row_order=row_order,
                      margin_titles=True)
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
                ax.plot(average_to_draw['x'], average_to_draw['avg_normal'],
                        label=f"Protocol fetch - {average_to_draw['eaves_count']} eaves", color='r')
                ax.plot(average_to_draw['x'], average_to_draw['avg_tc'], label="TCP fetch", color='orange')

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
