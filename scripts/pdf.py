import os
import sys
import json

from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import prediction_analysis
import process

def print_overview(metrics):
    # Print out an overview of how many experiments were done for which parameters
    by_experiment = process.groupBy(metrics, "experiment")
    overall_experiments = {}
    for experiment, metrics in by_experiment.items():
        # pick one item
        sample = metrics[0]
        key = sample['eavesCount'] + "-" + sample['latencyMS'] + "ms" + "-" + sample['fileSize'] + "byte"
        overall_experiments[key] = overall_experiments.get(key, 0) + 1
    print(json.dumps(overall_experiments, indent=4))

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"

results_dir = dir_path + "/../../experiments/results"

if len(sys.argv) == 2:
    results_dir = sys.argv[1]

# target_dir = dir_path + "/../../experiments"
target_dir = results_dir

metrics, testcases = process.aggregate_metrics(results_dir)
by_latency = process.groupBy(metrics, "latencyMS")

metrics_by_experiment_type = process.groupBy(metrics, "exType")
metrics_by_dialer = process.groupBy(metrics, "dialer")

# print_overview(metrics) # this somehow consumes some of the metrics items in the given list

info_items = first_timestamp_estimator.aggregate_global_info(results_dir)
message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
# Only consider the messages received by Eavesdropper nodes
message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]


# Analyse all prediction rates for all topologies
# with PdfPages(target_dir + "/" + f"prediction_rates-overall.pdf") as export_pdf:
#     prediction_analysis.analyse_prediction_rates(message_items, info_items, export_pdf)

# Split per topology
messages_by_eavescount = process.groupBy(message_items, "eavesCount")
metrics_by_eavescount = process.groupBy(metrics, "eavesCount")

for eaves_count, metrics_for_eaves_count in metrics_by_eavescount.items():
    by_latency = process.groupBy(metrics_for_eaves_count, "latencyMS")
    with PdfPages(target_dir + "/" + f"time-to-fetch-{eaves_count}.pdf") as export_pdf_ttf:
        process.plot_time_to_fetch_per_topology(eaves_count, metrics_for_eaves_count)
        export_pdf_ttf.savefig(pad_inches=0.4, bbox_inches='tight')

    with PdfPages(target_dir + "/" + f"messages-{eaves_count}.pdf") as export_pdf_messages:
        process.plot_messages(eaves_count, by_latency)
        export_pdf_messages.savefig()

# with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
#     first_timestamp_estimator.plot_estimate(results_dir)
#     export_pdf.savefig()
