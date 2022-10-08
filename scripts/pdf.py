import os
import sys

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

agg, testcases = process.aggregate_results(results_dir)
byLatency = process.groupBy(agg, "latencyMS")
byNodeType = process.groupBy(agg, "nodeType")
byFileSize = process.groupBy(agg, "fileSize")
byBandwidth = process.groupBy(agg, "bandwidthMB")
byTopology = process.groupBy(agg, "topology")
byTricklingDelay = process.groupBy(agg, "tricklingDelay")

with PdfPages(target_dir + "/" + "prediction_rates.pdf") as export_pdf:
    info_items_for_topology = first_timestamp_estimator.aggregate_global_info(results_dir)
    message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
    # Only consider the messages received by Eavesdropper nodes
    message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]

    # Split per topology
    messages_by_topology = process.groupBy(message_items, "topology")
    info_items_by_topology = process.groupBy(info_items_for_topology, "topology")

    for topology, messages_for_topology in messages_by_topology.items():
        info_items_for_topology = info_items_by_topology[topology]
        # Analyse messages for topology and save to file
        prediction_analysis.analyse_and_save_to_file(topology, messages_for_topology, info_items_for_topology,
                                                     export_pdf)

# with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
#     first_timestamp_estimator.plot_estimate(results_dir)
#     export_pdf.savefig()

with PdfPages(target_dir + "/" + "time-to-fetch.pdf") as export_pdf:
    process.plot_time_to_fetch_grouped(byLatency)
    export_pdf.savefig()

with PdfPages(target_dir + "/" + "messages.pdf") as export_pdf:
    topology = list(byTopology.keys())[0]
    process.plot_messages(topology, byTricklingDelay)
    export_pdf.savefig()
