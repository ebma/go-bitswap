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
by_latency = process.groupBy(agg, "latencyMS")
byNodeType = process.groupBy(agg, "nodeType")
byFileSize = process.groupBy(agg, "fileSize")
byBandwidth = process.groupBy(agg, "bandwidthMB")
byTopology = process.groupBy(agg, "topology")
byTricklingDelay = process.groupBy(agg, "tricklingDelay")

info_items_for_topology = first_timestamp_estimator.aggregate_global_info(results_dir)
message_items = first_timestamp_estimator.aggregate_message_histories(results_dir)
# Only consider the messages received by Eavesdropper nodes
message_items = [item for item in message_items if item["nodeType"] == "Eavesdropper"]

# Split per topology
messages_by_topology = process.groupBy(message_items, "topology")
info_items_by_topology = process.groupBy(info_items_for_topology, "topology")

for topology, messages_for_topology in messages_by_topology.items():
    info_items_for_topology = info_items_by_topology[topology]
    with PdfPages(target_dir + "/" + f"prediction_rates-{topology}.pdf") as export_pdf_box:
        with PdfPages(target_dir + "/" + f"prediction_rates-{topology}-averaged.pdf") as export_pdf_averaged:
            # Analyse messages for topology and save to file
            prediction_analysis.analyse_and_save_to_file(topology, messages_for_topology,
                                                         info_items_for_topology,
                                                         export_pdf_box, export_pdf_averaged)

# with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
#     first_timestamp_estimator.plot_estimate(results_dir)
#     export_pdf.savefig()

for topology, topology_results in byTopology.items():
    with PdfPages(target_dir + "/" + f"time-to-fetch-{topology}.pdf") as export_pdf:
        by_latency = process.groupBy(topology_results, "latencyMS")
        process.plot_time_to_fetch_grouped_with_filesize(topology, by_latency)
        export_pdf.savefig()

for topology, topology_results in byTopology.items():
    with PdfPages(target_dir + "/" + f"messages-{topology}.pdf") as export_pdf:
        by_latency = process.groupBy(topology_results, "latencyMS")
        process.plot_messages(topology, by_latency)
        export_pdf.savefig()
