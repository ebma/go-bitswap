import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

import first_timestamp_estimator
import process


def analyse_prediction_rates_per_eaves(messages, info_items):
    """
    Analyse the prediction rates per number of eavesdroppers
    :param messages: The messages to use for prediction
    :param info_items: The info items emitted by the leech node containing info about the true source
    """
    # Store results for each experiment and trickling delay in a dict
    results = list()

    # Holds the items that describe the true target of the prediction
    prediction_targets = [item for item in info_items if item['type'] == 'LeechInfo']

    messages_by_eaves_count = process.group_by(messages, "eavesCount")
    for eavesCount, messages_for_eavesCount in messages_by_eaves_count.items():
        # Group by latency
        by_latency = process.group_by(messages_for_eavesCount, "latencyMS")
        for latency, messagesWithLatency in by_latency.items():
            # Group by experiments
            by_latency_and_experiment = process.group_by(messagesWithLatency, "experiment")
            for experiment, messagesWithExperiment in by_latency_and_experiment.items():
                by_trickling_delay_with_latency_and_experiment = process.group_by(messagesWithExperiment,
                                                                                 "tricklingDelay")
                # Group by delay
                for delay, messagesWithDelay in by_trickling_delay_with_latency_and_experiment.items():
                    targets = [item for item in prediction_targets if
                               item['experiment'] == experiment and item['latencyMS'] == latency and item[
                                   'tricklingDelay'] == delay and item[
                                   'eavesCount'] == eavesCount]
                    # Get the prediction rate
                    rate = first_timestamp_estimator.get_prediction_rate(messagesWithDelay, targets)
                    results.append(
                        {'latency': latency, 'experiment': experiment, 'delay': delay,
                         'eavesdroppers': eavesCount,
                         'rate': rate})

    df = pd.DataFrame({'Delay': [int(item['delay']) for item in results],
                       'Latency': [item['latency'] + ' ms' for item in results],
                       'Rate': [item['rate'] for item in results],
                       'Eavesdroppers': [item['eavesdroppers'] for item in results],
                       })

    plt.figure(figsize=(10, 10))
    sns.set_style("darkgrid", {"grid.color": ".6", "grid.linestyle": ":"})

    # Sort dataframe by eavesdroppers ascending
    df.sort_values(by=['Eavesdroppers', 'Delay'], ascending=True, inplace=True)

    hue_order = ["50 ms", "100 ms", "150 ms"]
    g = sns.FacetGrid(df, col="Eavesdroppers", hue="Latency", hue_order=hue_order, margin_titles=True)
    g.map(sns.lineplot, "Delay", "Rate")
    g.set(xlabel='Trickling delay (ms)', ylabel='Prediction rate', ylim=(0, 1.1))
    g.add_legend()
    sns.despine(offset=10, trim=False)
