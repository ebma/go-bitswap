import argparse
import json
import os

import matplotlib.pyplot as plt

dir_path = os.path.dirname(os.path.realpath(__file__))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-src', '--source', type=str, help='''
                        The file containing the global info of a run
                        ''')
    parser.add_argument('-rdir', '--rel-dir', type=str, help='''
                        Relative result directory to process
                        ''')
    parser.add_argument('-dir', '--dir', type=str, help='''
                        Result directory to process
                        ''')

    return parser.parse_args()


def aggregate_global_info(results_dir):
    aggregated_items = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "globalInfo.out":
                result_file = open(filepath, 'r')
                for l in result_file.readlines():
                    aggregated_items.append(process_info_line(l))
    return aggregated_items


def aggregate_message_histories(results_dir):
    aggregated_items = []
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "messageHistory.out":
                result_file = open(filepath, 'r')
                for l in result_file.readlines():
                    aggregated_items.append(process_message_line(l))
    return aggregated_items


def process_info_line(l):
    l = json.loads(l)
    item = l
    if 'meta' in l:
        name = l['meta'].split("/")
        for attr in name:
            attr = attr.split(":")
            item[attr[0]] = attr[1]
    return item


def process_message_line(l):
    l = json.loads(l)
    name = l['meta'].split("/")
    item = l
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    item['ts'] = l['ts']
    return item


class FirstTimestampEstimator:
    def __init__(self, messages):
        self.messages = messages

    def predict(self, permutation, run, cid):
        run_messages = [m for m in self.messages if m['run'] == run and m['permutationIndex'] == permutation]
        # filter messages related to target cid
        cid_messages = [m for m in run_messages if cid in m['message']['wants']]
        cid_messages.sort(key=lambda x: x['ts'])
        prediction = cid_messages[0]['sender']
        return prediction


def plot_prediction_accuracy(prediction_results):
    print(prediction_results)

    prediction_results.sort(key=lambda x: x['latency'])

    plt.figure()
    unique_latencies = list(set([r['latency'] for r in prediction_results]))
    for latency in unique_latencies:
        latency_results = [r for r in prediction_results if r['latency'] == latency]
        latency_results.sort(key=lambda x: x['delay'])
        # x-axis
        delays = [r['delay'] for r in latency_results]
        # y-axis
        accuracy = [r['prediction_rate'] for r in latency_results]
        plt.plot(delays, accuracy, label=f"latency: {latency}ms")

    plt.title("Prediction accuracy")
    plt.xlabel("Trickling Delay (ms)")
    plt.ylabel("Prediction rate")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    args = parse_args()

    results_dir = dir_path + '/results'
    if args.dir:
        results_dir = args.dir
    elif args.rel_dir:
        results_dir = dir_path + '/' + args.rel_dir

    info_items = aggregate_global_info(results_dir)
    node_info_items = [item for item in info_items if item['type'] == 'NodeInfo']
    leech_target_items = [item for item in info_items if item['type'] == 'LeechInfo']

    message_items = aggregate_message_histories(results_dir)

    eavesdropper_nodes = [item for item in node_info_items if item['nodeType'] == 'Eavesdropper']
    eavesdropper_node_ids = [node['nodeId'] for node in eavesdropper_nodes]
    # message history of the eavesdropper nodes
    eavesdropper_message_items = [item for item in message_items if item['receiver'] in eavesdropper_node_ids]

    estimator = FirstTimestampEstimator(eavesdropper_message_items)

    correct_predictions = 0
    for leech_target in leech_target_items:
        permutation = leech_target['permutationIndex']
        run = leech_target['run']
        cid = leech_target['lookingFor']
        # the prediction estimated by the estimator
        prediction = estimator.predict(permutation, run, cid)
        # the leech that should be identified by the estimator
        target = leech_target['peer']

        leech_target['prediction'] = prediction

        if prediction == target:
            print("Prediction correct for run", run, "of permutation", permutation, "looking for", cid, ":", prediction)
            correct_predictions += 1
            leech_target['predictionCorrect'] = True
        else:
            leech_target['predictionCorrect'] = False
            print("Prediction incorrect for run", run, "looking for", cid, ":", prediction, "instead of", target)


    print(leech_target_items)

    prediction_results = list()
    # split by latency
    unique_latencies = list(set([item['latencyMS'] for item in leech_target_items]))
    unique_latencies.sort()
    for latency in unique_latencies:
        latency_items = [item for item in leech_target_items if item['latencyMS'] == latency]
        correct_predictions = len([item for item in latency_items if item['predictionCorrect']])
        prediction_rate = correct_predictions / len(latency_items)
        print("Prediction rate for latency", latency, ":", prediction_rate)

        # split by delay
        unique_delays = list(set([item['tricklingDelay'] for item in latency_items]))
        for delay in unique_delays:
            delay_items = [item for item in latency_items if item['tricklingDelay'] == delay]
            correct_predictions = len([item for item in delay_items if item['predictionCorrect']])
            prediction_rate = correct_predictions / len(delay_items)
            print("Prediction rate for latency", latency, "with delay", delay, ":", prediction_rate)

            prediction_results.append({'latency': latency, 'delay': delay, 'prediction_rate': prediction_rate})

    plot_prediction_accuracy(prediction_results)
