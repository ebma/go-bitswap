import os
import sys

from matplotlib.backends.backend_pdf import PdfPages

import first_timestamp_estimator
import prediction_analysis
import process

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"
if len(sys.argv) == 2:
    filename = sys.argv[1] + ".pdf"

results_dir = dir_path + "/../../experiments/results"
target_dir = dir_path + "/../../experiments"

agg, testcases = process.aggregate_results(results_dir)
byLatency = process.groupBy(agg, "latencyMS")
byNodeType = process.groupBy(agg, "nodeType")
byFileSize = process.groupBy(agg, "fileSize")
byBandwidth = process.groupBy(agg, "bandwidthMB")
byTopology = process.groupBy(agg, "topology")
byTricklingDelay = process.groupBy(agg, "tricklingDelay")

with PdfPages(target_dir + "/" + "prediction_rates.pdf") as export_pdf:
    prediction_analysis.analyse_and_save_to_file(results_dir, export_pdf)

with PdfPages(target_dir + "/" + "prediction_rates_agg.pdf") as export_pdf:
    first_timestamp_estimator.plot_estimate(results_dir)
    export_pdf.savefig()

with PdfPages(target_dir + "/" + "time-to-fetch.pdf") as export_pdf:
    latency = list(byLatency.keys())[0]
    process.plot_trickling_delays(latency, byTricklingDelay)
    export_pdf.savefig()

with PdfPages(target_dir + "/" + "messages.pdf") as export_pdf:
    topology = list(byTopology.keys())[0]
    process.plot_messages(topology, byTricklingDelay)
    export_pdf.savefig()
