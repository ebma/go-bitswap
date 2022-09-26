import process
import os
import sys
import first_timestamp_estimator
from matplotlib.backends.backend_pdf import PdfPages

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"
if len(sys.argv) == 2:
    filename = sys.argv[1] + ".pdf"


with PdfPages(dir_path + "/../experiments/" + filename) as export_pdf:
    results_dir = dir_path + "/../experiments/results"

    agg, testcases = process.aggregate_results(results_dir)
    byLatency = process.groupBy(agg, "latencyMS")
    byNodeType = process.groupBy(agg, "nodeType")
    byFileSize = process.groupBy(agg, "fileSize")
    byBandwidth = process.groupBy(agg, "bandwidthMB")
    byTopology = process.groupBy(agg, "topology")
    byTricklingDelay = process.groupBy(agg, "tricklingDelay")

    # There will only be one latency and topology in the results
    latency = list(byLatency.keys())[0]
    topology = list(byTopology.keys())[0]

    first_timestamp_estimator.plot_estimate(results_dir)
    export_pdf.savefig()
    process.plot_trickling_delays(latency, byTricklingDelay)
    export_pdf.savefig()
    # export_pdf.savefig(pad_inches=0.4, bbox_inches='tight')
    process.plot_messages(topology, byTricklingDelay)
    export_pdf.savefig()
