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


def analyse_average_messages(metrics, export_pdf):
    metrics_by_eaves_count = process.groupBy(metrics, "eavesCount")
    combined_frame = pd.DataFrame()
    for eaves_count, metrics_for_eaves_count in metrics_by_eaves_count.items():
        df = process.create_average_messages_dataframe(metrics_for_eaves_count, eaves_count)
        combined_frame = pd.concat([combined_frame, df])

    process.plot_messages_overall(combined_frame)
    export_pdf.savefig(pad_inches=0.4, bbox_inches='tight')


def create_pdfs():
    dir_path = os.path.dirname(os.path.realpath(__file__))

    results_dir = dir_path + "/../../experiments/results"

    if len(sys.argv) == 2:
        results_dir = sys.argv[1]

    # target_dir = dir_path + "/../../experiments"
    target_dir = results_dir

    # Load all metrics (ttf, duplicate blocks, ...)
    metrics, testcases = process.aggregate_metrics(results_dir)

    # Load the messages
    message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
    # Only consider the messages received by Eavesdropper nodes
    message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]
    # Load the info items containing the meta info about everly leech fetch
    info_items = first_timestamp_estimator.aggregate_global_info(results_dir)

    # print_overview(metrics) # this somehow consumes some of the metrics items in the given list

    # with PdfPages(target_dir + "/" + f"prediction_rates-overall.pdf") as export_pdf_prediction_rates:
    #     analyse_prediction_rates(message_items, info_items, export_pdf_prediction_rates)

    # with PdfPages(target_dir + "/" + f"time-to-fetch.pdf") as export_pdf_ttf:
    #     analyse_ttfb(metrics, target_dir, export_pdf_ttf)

    with PdfPages(target_dir + "/" + f"messages.pdf") as export_pdf_messages:
        # Pass metrics to analyse average messages (per type)
        analyse_average_messages(metrics, export_pdf_messages)


if __name__ == '__main__':
    create_pdfs()
