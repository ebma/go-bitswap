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


def process_info_line(line, experiment_id):
    line = json.loads(line)
    item = line
    # assume trickle experiment by default
    item['exType'] = 'trickle'
    item['dialer'] = 'edge'
    if 'meta' in line:
        name = line['meta'].split("/")
        for attr in name:
            attr = attr.split(":")
            item[attr[0]] = attr[1]
    if 'topology' in item:
        item['eavesCount'] = item['topology'].split('-')[-1][0]
    item['experiment'] = experiment_id
    return item


def aggregate_global_info(results_dir):
    aggregated_items = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "globalInfo.out":
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for line in result_file.readlines():
                    aggregated_items.append(process_info_line(line, experiment_id))
    return aggregated_items


def process_message_line(line, experiment_id):
    line = json.loads(line)
    name = line['meta'].split("/")
    item = line
    # assume trickle experiment by default
    item['exType'] = 'trickle'
    item['dialer'] = 'edge'
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    if 'topology' in item:
        item['eavesCount'] = item['topology'].split('-')[-1][0]
    item['ts'] = line['ts']
    item['experiment'] = experiment_id
    return item


def aggregate_message_histories(results_dir):
    aggregated_items = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "messageHistory.out":
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for line in result_file.readlines():
                    aggregated_items.append(process_message_line(line, experiment_id))
    return aggregated_items


def process_metric_line(line, experiment_id):
    line = json.loads(line)
    name = line["name"].split('/')
    value = (line["measures"])["value"]
    # set default values
    item = {'eavesCount': '0', 'exType': 'trickle', 'dialer': 'edge', 'tricklingDelay': '0'}
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    item["value"] = value
    item['experiment'] = experiment_id
    return item


def aggregate_metrics(results_dir):
    res = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "results.out":
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for l in result_file.readlines():
                    res.append(process_metric_line(l, experiment_id))
    return res, len(os.listdir(results_dir))


def group_by(agg, metric):
    res = {}
    for item in agg:
        if not item[metric] in res:
            res[item[metric]] = []
        res[item[metric]].append(item)
    return res
