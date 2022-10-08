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
                experiment_id = filepath.split("/")[-4]  # use testground experiment ID
                result_file = open(filepath, 'r')
                for line in result_file.readlines():
                    aggregated_items.append(process_info_line(line, experiment_id))
    return aggregated_items


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


def process_info_line(line, experiment_id):
    line = json.loads(line)
    item = line
    if 'meta' in line:
        name = line['meta'].split("/")
        for attr in name:
            attr = attr.split(":")
            item[attr[0]] = attr[1]
    item['experiment'] = experiment_id
    return item


def process_message_line(line, experiment_id):
    line = json.loads(line)
    name = line['meta'].split("/")
    item = line
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    item['ts'] = line['ts']
    item['experiment'] = experiment_id
    return item


class FirstTimestampEstimator:
    def __init__(self, messages):
        self.messages = messages

    def predict(self, permutation, run, cid):
        run_messages = [m for m in self.messages if m['run'] == run and m['permutationIndex'] == permutation]
        # filter messages related to target cid
        cid_messages = [m for m in run_messages if cid in m['message']['wants']]
        cid_messages.sort(key=lambda x: x['ts'])
        if len(cid_messages) == 0:
            return None
        prediction = cid_messages[0]['sender']
        return prediction


def plot_prediction_accuracy(topology, prediction_results, ax):
    prediction_results.sort(key=lambda x: x['latency'])

    unique_latencies = list(set([r['latency'] for r in prediction_results]))
    for latency in unique_latencies:
        latency_results = [r for r in prediction_results if r['latency'] == latency]
        latency_results.sort(key=lambda x: int(x['delay']))
        # x-axis
        delays = [r['delay'] for r in latency_results]
        # y-axis
        accuracy = [r['prediction_rate'] for r in latency_results]
        ax.plot(delays, accuracy, label=f"latency: {latency}ms")
        ax.scatter(delays, accuracy, s=100)

    ax.set_title("Topology " + topology)
    ax.set(xlabel='Trickling Delay (ms)', ylabel='Prediction rate')
    # ax.xlabel("Trickling Delay (ms)")
    # ax.ylabel("Prediction rate")
    ax.grid(True)
    ax.legend()


def get_prediction_rate(messages_with_delay, targets):
    estimator = FirstTimestampEstimator(messages_with_delay)
    correct_predictions = 0
    for target in targets:
        prediction = estimator.predict(target['permutationIndex'], target['run'], target['lookingFor'])
        target['prediction'] = prediction
        target['prediction_correct'] = prediction == target['peer']

        if target['prediction_correct']:
            correct_predictions += 1

    # Return the prediction rate
    return correct_predictions / len(targets)


def plot_estimate(results_dir):
    info_items = aggregate_global_info(results_dir)
    node_info_items = [item for item in info_items if item['type'] == 'NodeInfo']
    leech_target_items = [item for item in info_items if item['type'] == 'LeechInfo']

    message_items = aggregate_message_histories(results_dir)

    eavesdropper_nodes = [item for item in node_info_items if item['nodeType'] == 'Eavesdropper']
    eavesdropper_node_ids = [node['nodeId'] for node in eavesdropper_nodes]
    # message history of the eavesdropper nodes
    # eavesdropper_message_items = [item for item in message_items if item['receiver'] in eavesdropper_node_ids]
    eavesdropper_message_items = [item for item in message_items if item['nodeType'] == 'Eavesdropper']

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
            correct_predictions += 1
            leech_target['predictionCorrect'] = True
        else:
            leech_target['predictionCorrect'] = False

    print("Overall prediction rate: ", correct_predictions, "/",
          len(leech_target_items), "=", correct_predictions / len(leech_target_items))

    unique_topologies = list(set([item['topology'] for item in leech_target_items]))
    unique_topologies.sort(reverse=True)

    fig, axs = plt.subplots(1, len(unique_topologies), figsize=(10, 5), sharey=True)
    if len(unique_topologies) > 1:
        for index, topology in enumerate(unique_topologies):
            prediction_results = list()
            # split by latency
            unique_latencies = list(set([item['latencyMS'] for item in leech_target_items]))
            unique_latencies.sort()

            leech_target_items_for_topology = [item for item in leech_target_items if item['topology'] == topology]
            for latency in unique_latencies:
                latency_items = [item for item in leech_target_items_for_topology if item['latencyMS'] == latency]
                correct_predictions = len([item for item in latency_items if item['predictionCorrect']])
                prediction_rate = correct_predictions / len(latency_items)
                print("Prediction rate for topology", topology, "with latency", latency, ":", prediction_rate)

                # split by delay
                unique_delays = list(set([item['tricklingDelay'] for item in latency_items]))
                for delay in unique_delays:
                    delay_items = [item for item in latency_items if item['tricklingDelay'] == delay]
                    correct_predictions = len([item for item in delay_items if item['predictionCorrect']])
                    prediction_rate = correct_predictions / len(delay_items)
                    print("Prediction rate for topology", topology, "with latency", latency, "with delay", delay, ":",
                          prediction_rate)

                    prediction_results.append({'latency': latency, 'delay': delay, 'prediction_rate': prediction_rate})

            plot_prediction_accuracy(topology, prediction_results, axs[index])
        fig.suptitle("Prediction accuracy for different topologies - (passive-leech-seed-eavesdropper)")
        plt.show()
    else:
        topology = unique_topologies[0]
        prediction_results = list()
        # split by latency
        unique_latencies = list(set([item['latencyMS'] for item in leech_target_items]))
        unique_latencies.sort()

        leech_target_items_for_topology = [item for item in leech_target_items if item['topology'] == topology]
        for latency in unique_latencies:
            latency_items = [item for item in leech_target_items_for_topology if item['latencyMS'] == latency]
            correct_predictions = len([item for item in latency_items if item['predictionCorrect']])
            prediction_rate = correct_predictions / len(latency_items)
            print("Prediction rate for topology", topology, "with latency", latency, ":", prediction_rate)

            # split by delay
            unique_delays = list(set([item['tricklingDelay'] for item in latency_items]))
            for delay in unique_delays:
                delay_items = [item for item in latency_items if item['tricklingDelay'] == delay]
                correct_predictions = len([item for item in delay_items if item['predictionCorrect']])
                prediction_rate = correct_predictions / len(delay_items)
                print("Prediction rate for topology", topology, "with latency", latency, "with delay", delay, ":",
                      prediction_rate)

                prediction_results.append({'latency': latency, 'delay': delay, 'prediction_rate': prediction_rate})

        plot_prediction_accuracy(topology, prediction_results, axs)

        fig.suptitle(f"Prediction accuracy for topology {topology} - (passive-leech-seed-eavesdropper)")


if __name__ == "__main__":
    args = parse_args()

    results_dir = dir_path + '/results'
    if args.dir:
        results_dir = args.dir
    elif args.rel_dir:
        results_dir = dir_path + '/' + args.rel_dir

    plot_estimate(results_dir)
    plt.show()
