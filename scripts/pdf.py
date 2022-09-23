import process
import os
import sys
from matplotlib.backends.backend_pdf import PdfPages

dir_path = os.path.dirname(os.path.realpath(__file__))
filename = "result.pdf"
if len(sys.argv) == 2:
    filename = sys.argv[1] + ".pdf"


with PdfPages(dir_path + "/../experiments/" + filename) as export_pdf:

    agg, testcases = process.aggregate_results(dir_path + "/../experiments/results")
    byLatency = process.groupBy(agg, "latencyMS")
    byNodeType = process.groupBy(agg, "nodeType")
    byFileSize = process.groupBy(agg, "fileSize")
    byBandwidth = process.groupBy(agg, "bandwidthMB")
    byTopology = process.groupBy(agg, "topology")
    byTricklingDelay = process.groupBy(agg, "tricklingDelay")

    process.plot_latency(byLatency, byTricklingDelay, byFileSize)
    export_pdf.savefig(pad_inches=0.4, bbox_inches='tight')
    process.plot_messages(byFileSize, byTopology)
    export_pdf.savefig()
    process.plot_bw_overhead(byFileSize, byTopology)
    export_pdf.savefig()
    # process.plot_througput(byLatency, byBandwidth, byFileSize, byTopology, testcases)
    # export_pdf.savefig()
    process.plot_want_messages(byFileSize, byTopology)
    export_pdf.savefig()
    # process.plot_tcp_latency(byLatency, byBandwidth, byFileSize)
    # export_pdf.savefig()
