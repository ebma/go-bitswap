import argparse
import json
import os

dir_path = os.path.dirname(os.path.realpath(__file__))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--plots', nargs='+', help='''
                        One or more plots to be shown.
                        Available: latency, throughput, overhead, messages, wants, tcp.
                        ''')
    parser.add_argument('-o', '--outputs', nargs='+', help='''
                        One or more outputs to be shown.
                        Available: data
                        ''')
    parser.add_argument('-dir', '--dir', type=str, help='''
                        Result directory to process
                        ''')

    return parser.parse_args()


def process_metric_line(line, experiment_id):
    line = json.loads(line)
    name = line["name"].split('/')
    value = (line["measures"])["value"]
    # set default values
    item = {'eavesCount': '0', 'exType': 'trickle', 'dialer': 'edge', 'tricklingDelay': '0'}
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    # for compatibility with old results
    if 'topology' in item:
        item['eavesCount'] = item['topology'].split('-')[-1][0]
    item["value"] = value
    item['experiment'] = experiment_id
    return item


def aggregate_metrics(results_dir):
    res = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "results.out":
                # print (filepath)
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for l in result_file.readlines():
                    res.append(process_metric_line(l, experiment_id))
    return res, len(os.listdir(results_dir))


def groupBy(agg, metric):
    res = {}
    for item in agg:
        if not item[metric] in res:
            res[item[metric]] = []
        res[item[metric]].append(item)
    return res


def autolabel(ax, rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
