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

    agg, testcases = process.aggregate_results(results_dir)
    byLatency = process.groupBy(agg, "latencyMS")
    byNodeType = process.groupBy(agg, "nodeType")
    byFileSize = process.groupBy(agg, "fileSize")
    byBandwidth = process.groupBy(agg, "bandwidthMB")
    byTopology = process.groupBy(agg, "topology")
    byTricklingDelay = process.groupBy(agg, "tricklingDelay")
    byExperiment = process.groupBy(agg, "experiment")



    first_timestamp_estimator.plot_estimate(results_dir)
    export_pdf.savefig()
    # process.plot_trickling_delays(latency, byTricklingDelay)
    # export_pdf.savefig()
