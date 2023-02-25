import os
import sys

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from numpy import sqrt

import message_metrics_analysis
import prediction_analysis
import process
import ttf_analysis

fig_width_pt = 246.0
inches_per_pt = 1.0 / 72.27  # Convert pt to inch
golden_mean = (sqrt(5) - 1.0) / 2.0  # Aesthetic ratio
fig_width = fig_width_pt * inches_per_pt  # width in inches
fig_height = fig_width * golden_mean  # height in inches
fig_size = [fig_width, fig_height]
params = {'backend': 'ps',
          'axes.labelsize': 10,
          'legend.fontsize': 10,
          'xtick.labelsize': 8,
          'ytick.labelsize': 8,
          'text.usetex': False,
          'figure.figsize': fig_size}
plt.rcParams.update(params)


def analyse_prediction_rates(message_items, info_items):
    """
    Analyse the prediction rates for all topologies
    :param message_items: the message items received by the eavesdroppers
    :param info_items: the info items emitted by the leech node. This is used to know the true source of the message
    """
    prediction_analysis.analyse_prediction_rates_per_eaves(message_items, info_items)


def analyse_ttf_for_0_eaves(metrics):
    """
    Analyse the time to fetch for all topologies with 0 eavesdroppers
    :param metrics: the metrics to analyse
    """
    metrics_by_eavescount = process.group_by(metrics, "eavesCount")

    metrics_for_eaves_count = None
    if "0" in metrics_by_eavescount:
        # Only consider the metrics for 0 eavesdroppers
        metrics_for_eaves_count = metrics_by_eavescount["0"]

    if metrics_for_eaves_count is None:
        print("No metrics for 0 eavesdroppers")
        return

    df, averages = ttf_analysis.create_ttf_dataframe(metrics_for_eaves_count, 0, False)
    ttf_analysis.plot_time_to_fetch_per_extype(df)


def analyse_average_messages_comparing_0_delay(metrics):
    """
    Analyse the average messages for all topologies with 0 eavesdroppers
    :param metrics: the metrics to analyse
    """
    metrics_by_eaves_count = process.group_by(metrics, "eavesCount")

    # Only consider the metrics for 0 eavesdroppers
    metrics_for_eaves_count = None
    if "0" in metrics_by_eaves_count:
        # Only consider the metrics for 0 eavesdroppers
        metrics_for_eaves_count = metrics_by_eaves_count["0"]

    if metrics_for_eaves_count is None:
        print("No metrics for 0 eavesdroppers")
        return

    df = message_metrics_analysis.create_average_messages_dataframe_compact(metrics_for_eaves_count, 0)

    message_metrics_analysis.plot_messages_for_0_trickling(df)


def create_pdfs():
    """
    Create the pdfs for the plots
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))

    results_dir = dir_path + "/../experiments/results"

    if len(sys.argv) == 2:
        results_dir = sys.argv[1]

    target_dir = results_dir

    # Load all metrics (ttf, duplicate blocks, ...)
    metrics, testcases = process.aggregate_metrics(results_dir)

    # Load the messages
    message_items = process.aggregate_message_histories(results_dir)
    # Only consider the messages received by Eavesdropper nodes
    message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]
    # Load the info items containing the meta info about everly leech fetch
    info_items = process.aggregate_global_info(results_dir)

    # Create a PDF file for each dialer
    dialers = ["center", "edge"]

    sns.set(font_scale=1.1)

    for dialer in dialers:
        message_items_for_dialer = [item for item in message_items if item["dialer"] == dialer]
        info_items_for_dialer = [item for item in info_items if item["dialer"] == dialer]
        metrics_for_dialer = [item for item in metrics if item["dialer"] == dialer]

        with PdfPages(target_dir + "/" + f"prediction_rates-overall-{dialer}.pdf") as export_pdf_prediction_rates:
            if len(message_items_for_dialer) > 0 and len(info_items_for_dialer) > 0:
                analyse_prediction_rates(message_items_for_dialer, info_items_for_dialer)
                export_pdf_prediction_rates.savefig(pad_inches=0.4, bbox_inches='tight')

        with PdfPages(target_dir + "/" + f"time-to-fetch-{dialer}.pdf") as export_pdf_ttf:
            if len(metrics_for_dialer) > 0:
                analyse_ttf_for_0_eaves(metrics_for_dialer)
                export_pdf_ttf.savefig(pad_inches=0.4, bbox_inches='tight')

        with PdfPages(target_dir + "/" + f"average-messages-{dialer}.pdf") as export_pdf_messages:
            if len(metrics_for_dialer) > 0:
                analyse_average_messages_comparing_0_delay(metrics_for_dialer)
                export_pdf_messages.savefig(pad_inches=0.4, bbox_inches='tight')


if __name__ == '__main__':
    create_pdfs()
