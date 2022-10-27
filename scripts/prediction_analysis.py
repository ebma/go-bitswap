import os

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import process


def analyse_prediction_rates(messages, info_items, export_pdf):
    # Store results for each experiment and trickling delay in a dict
    results = list()

    # Holds the items that describe the true target of the prediction
    prediction_targets = [item for item in info_items if item['type'] == 'LeechInfo']

    messages_by_topology = process.groupBy(messages, "topology")
    for topology, messages_for_topology in messages_by_topology.items():
        by_latency = process.groupBy(messages_for_topology, "latencyMS")

        # Get prediction rates for each latency (contains multiple experiments)
        for latency, messagesWithLatency in by_latency.items():
            # Group by experiments
            by_latency_and_experiment = process.groupBy(messagesWithLatency, "experiment")
            for experiment, messagesWithExperiment in by_latency_and_experiment.items():
                by_file_size = process.groupBy(messagesWithExperiment, "fileSize")
                for file_size, messagesWithFileSize in by_file_size.items():
                    by_trickling_delay_with_latency_and_experiment = process.groupBy(messagesWithFileSize,
                                                                                     "tricklingDelay")

                    # Group by delay
                    for delay, messagesWithDelay in by_trickling_delay_with_latency_and_experiment.items():
                        targets = [item for item in prediction_targets if
                                   item['experiment'] == experiment and item['latencyMS'] == latency and item[
                                       'tricklingDelay'] == delay and item['fileSize'] == file_size and item[
                                       'topology'] == topology]
                        rate = first_timestamp_estimator.get_prediction_rate(messagesWithDelay, targets)
                        eavesdropper_count = topology[-2]
                        results.append(
                            {'latency': latency, 'experiment': experiment, 'delay': delay,
                             'eavesdroppers': eavesdropper_count,
                             'rate': rate, 'file_size': file_size})

    df = pd.DataFrame({'Delay': [item['delay'] for item in results],
                       'Latency (ms)': [item['latency'] for item in results],
                       'Rate': [item['rate'] for item in results],
                       'Eavesdroppers': [item['eavesdroppers'] for item in results],
                       'Filesize': [item['file_size'] for item in results],
                       }, dtype=float)

    dd = pd.melt(df, id_vars=['Delay', 'Latency (ms)', 'Filesize', 'Eavesdroppers'], value_vars=['Rate'])

    plt.figure(figsize=(10, 10))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})

    # Maybe turn some cols to integer type
    g = sns.FacetGrid(df, col="Filesize", row="Eavesdroppers", hue="Latency (ms)", margin_titles=True)
    g.map(sns.lineplot, "Delay", "Rate")
    g.set(xlabel='Trickling delay (ms)', ylabel='Prediction rate', ylim=(0, 1))
    g.add_legend()
    sns.despine(offset=10, trim=False)
    export_pdf.savefig(g.figure, pad_inches=0.4, bbox_inches='tight')

    plt.close('all')


# The message_items are already filtered to only contain the Eavesdropper messages
def analyse_and_save_to_file_single(topology, message_items, info_items, export_pdf_averaged):
    # Store results for each experiment and trickling delay in a dict
    results = list()

    # Holds the items that describe the true target of the prediction
    prediction_targets = [item for item in info_items if item['type'] == 'LeechInfo']

    by_latency = process.groupBy(message_items, "latencyMS")
    # Get prediction rates for each latency (contains multiple experiments)
    for latency, messagesWithLatency in by_latency.items():
        # Group by experiments
        by_latency_and_experiment = process.groupBy(messagesWithLatency, "experiment")
        for experiment, messagesWithExperiment in by_latency_and_experiment.items():
            by_file_size = process.groupBy(messagesWithExperiment, "fileSize")
            for file_size, messagesWithFileSize in by_file_size.items():
                by_trickling_delay_with_latency_and_experiment = process.groupBy(messagesWithFileSize, "tricklingDelay")

                # Group by delay
                for delay, messagesWithDelay in by_trickling_delay_with_latency_and_experiment.items():
                    targets = [item for item in prediction_targets if
                               item['experiment'] == experiment and item['latencyMS'] == latency and item[
                                   'tricklingDelay'] == delay and item['fileSize'] == file_size]
                    rate = first_timestamp_estimator.get_prediction_rate(messagesWithDelay, targets)
                    results.append({'latency': latency, 'experiment': experiment, 'delay': delay, 'rate': rate,
                                    'file_size': file_size})

    df = pd.DataFrame({'Delay': [item['delay'] for item in results],
                       'Latency (ms)': [item['latency'] for item in results],
                       'Rate': [item['rate'] for item in results],
                       }, dtype=float)

    dd = pd.melt(df, id_vars=['Delay', 'Latency (ms)'], value_vars=['Rate'])

    print(dd)
    plt.figure(figsize=(10, 10))
    sns.set_theme(style="ticks", palette="husl")
    splot = sns.boxplot(x='Delay', y='value', hue='Latency (ms)', data=dd)
    sns.despine(offset=10, trim=False)

    splot.set(xlabel='Trickling delay (ms)', ylabel='Prediction rate',
              title=f'Prediction rate for different trickling delays with topology {topology}', ylim=(0, 1))

    plt.grid()
    plt.figure(figsize=(10, 10))
    splot = sns.lineplot(x='Delay', y='value', hue='Latency (ms)', data=dd)
    sns.despine(offset=10, trim=False)

    splot.set(xlabel='Trickling delay (ms)', ylabel='Prediction rate',
              title=f'Prediction rate for different trickling delays with topology {topology}', ylim=(0, 1))

    plt.grid()
    export_pdf_averaged.savefig(splot.figure, pad_inches=0.4, bbox_inches='tight')

    plt.close('all')


if __name__ == '__main__':
    dir_path = os.path.dirname(os.path.realpath(__file__))
    results_dir = dir_path + "/../../experiments/results"
    target_dir = dir_path + "/../../experiments"

    info_items = first_timestamp_estimator.aggregate_global_info(results_dir)
    message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
    # Only consider the messages received by Eavesdropper nodes
    message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]

    with PdfPages(target_dir + "/" + "prediction_rates-averaged.pdf") as export_pdf:
        analyse_prediction_rates(message_items, info_items, export_pdf)

    # Split per topology
    # messages_by_topology = process.groupBy(message_items, "topology")
    # info_items_by_topology = process.groupBy(info_items, "topology")
    #
    # for topology, messages_for_topology in messages_by_topology.items():
    #     info_items_for_topology = info_items_by_topology[topology]
    #     with PdfPages(target_dir + "/" + "prediction_rates-averaged.pdf") as export_pdf_averaged:
    #         analyse_and_save_to_file_single(topology, messages_for_topology, info_items_for_topology,
    #                                         export_pdf_averaged)
