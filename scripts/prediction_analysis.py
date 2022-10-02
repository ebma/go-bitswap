import os
import sys

from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import process

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"
directory_path = dir_path + "/../../../experiments/results"
if len(sys.argv) == 2:
    directory_path = sys.argv[1]

with PdfPages(directory_path + filename) as export_pdf:
    results_dir = directory_path

    # Store results for each experiment and trickling delay in a dict
    results = {}

    # TODO derive experiment ID from testground directory name. Use that to group results
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
                results[latency][experiment][delay] = rate

    print(results)
    # first_timestamp_estimator.plot_estimate(results_dir)
    # export_pdf.savefig()
    # process.plot_trickling_delays(latency, byTricklingDelay)
    # export_pdf.savefig()
