import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

import first_timestamp_estimator
import process


def analyse_and_save_to_file(results_dir, export_pdf):
    # Store results for each experiment and trickling delay in a dict
    results = list()

    info_items = first_timestamp_estimator.aggregate_global_info(results_dir)
    message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)

    # Holds the items that describe the true target of the prediction
    predictionTargets = [item for item in info_items if item['type'] == 'LeechInfo']

    byLatency = process.groupBy(message_items, "latencyMS")
    # Get prediction rates for each latency (contains multiple experiments)
    for latency, messagesWithLatency in byLatency.items():
        # Group by experiments
        byLatencyAndExperiment = process.groupBy(messagesWithLatency, "experiment")
        for experiment, messagesWithExperiment in byLatencyAndExperiment.items():
            byTricklingDelayWithLatencyAndExperiment = process.groupBy(messagesWithExperiment, "tricklingDelay")

            # Group by delay
            for delay, messagesWithDelay in byTricklingDelayWithLatencyAndExperiment.items():
                targets = [item for item in predictionTargets if
                           item['experiment'] == experiment and item['latencyMS'] == latency and item[
                               'tricklingDelay'] == delay]
                rate = first_timestamp_estimator.get_prediction_rate(messagesWithDelay, targets)
                # results[latency][experiment][delay] = rate
                results.append({'latency': latency, 'experiment': experiment, 'delay': delay, 'rate': rate})
                # if latency not in results:
                #     results[latency] = list()
                # results[latency].append(
                #     {'experiment': experiment, 'delay': delay, 'rate': rate})

    # artificially amend results
    def map_function(x, modifier, name):
        y = {}
        y['rate'] = x['rate'] + modifier
        y['experiment'] = name
        y['delay'] = x['delay']
        y['latency'] = str(int(x['latency']) + 50)
        return y

    other_results = list(map(lambda x: map_function(x, 0.1, 'asdf'), results))
    results.extend(other_results)
    other_results = list(map(lambda x: map_function(x, -0.1, 'befg'), results))
    results.extend(other_results)
    other_results = list(map(lambda x: map_function(x, -0.2, 'xyz'), results))
    results.extend(other_results)

    df = pd.DataFrame({'Delay': [item['delay'] for item in results], \
                       'Latency (ms)': [item['latency'] for item in results], \
                       'Rate': [item['rate'] for item in results]}, dtype=float)

    dd = pd.melt(df, id_vars=['Delay', 'Latency (ms)'], value_vars=['Rate'])

    plt.figure(figsize=(10, 10))
    sns.set_theme(style="ticks", palette="husl")
    splot = sns.boxplot(x='Delay', y='value', hue='Latency (ms)', data=dd)
    sns.despine(offset=10, trim=False)

    splot.set(xlabel='Trickling delay (ms)', ylabel='Prediction rate',
              title='Prediction rate for different trickling delays', ylim=(0, 1))

    plt.grid()
    export_pdf.savefig(splot.figure, pad_inches=0.4, bbox_inches='tight')
