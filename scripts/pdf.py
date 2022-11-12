import json
import os
import sys

import pandas as pd
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


def analyse_prediction_rates(message_items, info_items, export_pdf):
    # Analyse all prediction rates for all topologies
    prediction_analysis.analyse_prediction_rates(message_items, info_items, export_pdf)


def analyse_ttfb(metrics, target_dir, export_pdf):
    metrics_by_eavescount = process.groupBy(metrics, "eavesCount")

    # unify everything in one plot
    combined_frame = pd.DataFrame()
    all_averages = list()
    for eaves_count, metrics_for_eaves_count in metrics_by_eavescount.items():
        df, averages = process.create_ttf_dataframe(metrics_for_eaves_count, eaves_count)
        combined_frame = pd.concat([combined_frame, df])
        all_averages.append(averages)

    process.plot_time_to_fetch_per_topology(combined_frame, all_averages)
    export_pdf.savefig(pad_inches=0.4, bbox_inches='tight')


def analyse_messages(messages, export_pdf):
    messages_by_eavescount = process.groupBy(messages, "eavesCount")
    for eaves_count, messages_for_eaves_count in messages_by_eavescount.items():
        process.plot_messages_per_eaves(messages_for_eaves_count, info_items)
        export_pdf.savefig(pad_inches=0.4, bbox_inches='tight')


#     with PdfPages(target_dir + "/" + f"messages-{eaves_count}.pdf") as export_pdf_messages:
#         process.plot_messages(eaves_count, by_latency)
#         export_pdf_messages.savefig()
#     by_latency = process.groupBy(metrics_for_eaves_count, "latencyMS")
#         process.plot_time_to_fetch_per_topology(eaves_count, metrics_for_eaves_count)
#

# with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
#     first_timestamp_estimator.plot_estimate(results_dir)
#     export_pdf.savefig()


def create_pdfs():
    dir_path = os.path.dirname(os.path.realpath(__file__))

    results_dir = dir_path + "/../../experiments/results"

    if len(sys.argv) == 2:
        results_dir = sys.argv[1]

    # target_dir = dir_path + "/../../experiments"
    target_dir = results_dir

    metrics, testcases = process.aggregate_metrics(results_dir)
    by_latency = process.groupBy(metrics, "latencyMS")

    metrics_by_experiment_type = process.groupBy(metrics, "exType")
    metrics_by_dialer = process.groupBy(metrics, "dialer")

    # Split per topology
    # messages_by_eavescount = process.groupBy(message_items, "eavesCount")

    # print_overview(metrics) # this somehow consumes some of the metrics items in the given list

    info_items = first_timestamp_estimator.aggregate_global_info(results_dir)
    message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
    # Only consider the messages received by Eavesdropper nodes
    message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]

    with PdfPages(target_dir + "/" + f"prediction_rates-overall.pdf") as export_pdf:
        analyse_prediction_rates(message_items, info_items, export_pdf)

    with PdfPages(target_dir + "/" + f"time-to-fetch.pdf") as export_pdf:
        analyse_ttfb(metrics, target_dir, export_pdf)

    with PdfPages(target_dir + "/" + f"messages.pdf") as export_pdf:
        analyse_messages(message_items, export_pdf)


if __name__ == '__main__':
    create_pdfs()
