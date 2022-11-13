import json
import os
import sys

import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import message_metrics_analysis
import prediction_analysis
import process
import ttf_analysis


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


def analyse_prediction_rates(message_items, info_items):
    # Analyse all prediction rates for all topologies
    prediction_analysis.analyse_prediction_rates_per_eaves(message_items, info_items)


def analyse_ttf_for_0_eaves(metrics):
    metrics_by_eavescount = process.groupBy(metrics, "eavesCount")

    # Only consider the metrics for 0 eavesdroppers
    metrics_for_eaves_count = metrics_by_eavescount["0"]

    df, averages = ttf_analysis.create_ttf_dataframe(metrics_for_eaves_count, 0)
    ttf_analysis.plot_time_to_fetch_per_extype(df, averages)


def analyse_ttf_for_all(metrics):
    metrics_by_eavescount = process.groupBy(metrics, "eavesCount")

    # unify everything in one plot
    combined_frame = pd.DataFrame()
    all_averages = list()
    for eaves_count, metrics_for_eaves_count in metrics_by_eavescount.items():
        df, averages = ttf_analysis.create_ttf_dataframe(metrics_for_eaves_count, eaves_count)
        combined_frame = pd.concat([combined_frame, df])
        all_averages.append(averages)

    ttf_analysis.plot_time_to_fetch_for_all_eavescounts(combined_frame, all_averages)


def analyse_average_messages_comparing_0_delay(metrics):
    metrics_by_eaves_count = process.groupBy(metrics, "eavesCount")
    # Only consider the metrics for 0 eavesdroppers
    metrics_for_eaves_count = metrics_by_eaves_count["0"]
    df = message_metrics_analysis.create_average_messages_dataframe_compact(metrics_for_eaves_count, 0)

    message_metrics_analysis.plot_messages_for_0_trickling(df)


def analyse_average_messages_per_ex_type_and_all_delays(metrics, export_pdf):
    metrics_by_eaves_count = process.groupBy(metrics, "eavesCount")
    # Only consider the metrics for 0 eavesdroppers
    metrics_for_eaves_count = metrics_by_eaves_count["0"]
    df = message_metrics_analysis.create_average_messages_dataframe_long(metrics_for_eaves_count, 0)

    message_metrics_analysis.plot_messages_overall(df)
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

    # Create a PDF file for each dialer
    dialers = ["center", "edge"]
    for dialer in dialers:
        # TODO check if these contain all data
        message_items_for_dialer = [item for item in message_items if item["dialer"] == dialer]
        info_items_for_dialer = [item for item in info_items if item["dialer"] == dialer]
        metrics_for_dialer = [item for item in metrics if item["dialer"] == dialer]

        with PdfPages(target_dir + "/" + f"prediction_rates-overall-{dialer}.pdf") as export_pdf_prediction_rates:
            if len(message_items_for_dialer) > 0 and len(info_items_for_dialer) > 0:
                analyse_prediction_rates(message_items_for_dialer, info_items_for_dialer)
                export_pdf_prediction_rates.savefig(pad_inches=0.4, bbox_inches='tight')

        with PdfPages(target_dir + "/" + f"time-to-fetch-{dialer}.pdf") as export_pdf_ttf:
            if len(metrics_for_dialer) > 0:
                # analyse_ttf_for_all(metrics)
                analyse_ttf_for_0_eaves(metrics_for_dialer)
                export_pdf_ttf.savefig(pad_inches=0.4, bbox_inches='tight')

        with PdfPages(target_dir + "/" + f"average-messages-{dialer}.pdf") as export_pdf_messages:
            if len(metrics_for_dialer) > 0:
                # Pass metrics to analyse average messages (per type)
                # analyse_average_messages_per_ex_type_and_all_delays(metrics, export_pdf_messages)
                analyse_average_messages_comparing_0_delay(metrics_for_dialer)
                export_pdf_messages.savefig(pad_inches=0.4, bbox_inches='tight')


if __name__ == '__main__':
    create_pdfs()
