import os
import sys
import json

from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import prediction_analysis
import process

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"

results_dir = dir_path + "/../../experiments/results"

if len(sys.argv) == 2:
    results_dir = sys.argv[1]

# target_dir = dir_path + "/../../experiments"
target_dir = results_dir

metrics, testcases = process.aggregate_results(results_dir)
by_latency = process.groupBy(metrics, "latencyMS")
byNodeType = process.groupBy(metrics, "nodeType")
byFileSize = process.groupBy(metrics, "fileSize")
byBandwidth = process.groupBy(metrics, "bandwidthMB")
byTricklingDelay = process.groupBy(metrics, "tricklingDelay")

metrics_by_topology = process.groupBy(metrics, "topology")
# TODO maybe split also by dialer
# metrics_by_dialer = process.groupBy(metrics, "dialer")

# Print out an overview of how many experiments were done for which parameters
by_experiment = process.groupBy(metrics, "experiment")
overall_experiments = {}
for experiment, metrics in by_experiment.items():
    # pick one item
    sample = metrics[0]
    key = sample['topology'] + "-" + sample['latencyMS'] + "ms" + "-" + sample['fileSize'] + "byte"
    overall_experiments[key] = overall_experiments.get(key, 0) + 1
print(json.dumps(overall_experiments, indent=4))

info_items = first_timestamp_estimator.aggregate_global_info(results_dir)
message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
# Only consider the messages received by Eavesdropper nodes
message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]


# Analyse all prediction rates for all topologies
with PdfPages(target_dir + "/" + f"prediction_rates-overall.pdf") as export_pdf:
    prediction_analysis.analyse_prediction_rates(message_items, info_items, export_pdf)

# Split per topology
messages_by_topology = process.groupBy(message_items, "topology")

for topology, metrics_for_topology in metrics_by_topology.items():
    with PdfPages(target_dir + "/" + f"time-to-fetch-{topology}.pdf") as export_pdf:
        process.plot_time_to_fetch_grouped_with_filesize(topology, metrics_for_topology, export_pdf)

    with PdfPages(target_dir + "/" + f"messages-{topology}.pdf") as export_pdf:
        by_latency = process.groupBy(metrics_for_topology, "latencyMS")
        process.plot_messages(topology, by_latency)
        # TODO streamline this with the other things
        # Either pass export or save it afterwards
        # export_pdf.savefig()

# with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
#     first_timestamp_estimator.plot_estimate(results_dir)
#     export_pdf.savefig()
