import argparse
import json
import os

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
    item = {'source': l['id'], 'timestamp': l['timestamp'], 'value': l['info'], 'type': l['type']}
    return item


def process_message_line(l):
    l = json.loads(l)
    name = l['name'].split("/")
    item = l
    for attr in name:
        attr = attr.split(":")
        item[attr[0]] = attr[1]
    item['ts'] = l['ts']
    return item


class FirstTimestampEstimator:
    def __init__(self, messages):
        self.messages = messages

    def predict_source_of(self, cid):
        # filter messages related to target cid
        cid_messages = [m for m in run_messages if cid in m['message']['wants']]
        cid_messages.sort(key=lambda x: x['ts'])
        prediction = cid_messages[0]['sender']
        return prediction


if __name__ == "__main__":
    args = parse_args()

    results_dir = dir_path + '/results'
    if args.dir:
        results_dir = args.dir
    elif args.rel_dir:
        results_dir = dir_path + '/' + args.rel_dir

    info_items = aggregate_global_info(results_dir)
    node_info_items = [item for item in info_items if item['type'] == 'NodeInfo']
    leech_target_items = [item for item in info_items if item['type'] == 'LeechTarget']

    message_items = aggregate_message_histories(results_dir)

    eavesdropper_nodes = [item['value'] for item in node_info_items if item['value']['nodeType'] == 'Eavesdropper']
    eavesdropper_node_ids = [node['nodeId'] for node in eavesdropper_nodes]
    # message history of the eavesdropper nodes
    eavesdropper_message_items = [item for item in message_items if item['receiver'] in eavesdropper_node_ids]

    # group by tricklingDelay
    eavesdropper_message_items.sort(key=lambda x: x['tricklingDelay'])
    unique_delays = list(set([item['tricklingDelay'] for item in eavesdropper_message_items]))

    prediction_map = {}
    # predict the source grouped by the trickling delay
    for delay in unique_delays:
        items_with_delay = [item for item in eavesdropper_message_items if item['tricklingDelay'] == delay]
        unique_permutations_for_delay = list(set([item['permutationIndex'] for item in items_with_delay]))

        for permutation_index in unique_permutations_for_delay:
            correct_predictions = 0
            leech_targets_for_permutation = [item for item in leech_target_items if
                                             item['value']['permutationIndex'] == permutation_index]

            message_items_for_permutation = [item for item in items_with_delay if
                                             item['permutationIndex'] == permutation_index]

            for leech_target in leech_targets_for_permutation:
                permutation = leech_target['value']['permutationIndex']
                run = leech_target['value']['run']
                cid = leech_target['value']['lookingFor']

                # filter messages related to target permutation and run
                run_messages = [m for m in message_items_for_permutation if m['run'] == str(run)]
                estimator = FirstTimestampEstimator(run_messages)

                # the prediction estimated by the estimator
                prediction = estimator.predict_source_of(cid)
                # the leech that should be identified by the estimator
                target = leech_target['value']['peer']

                if prediction == target:
                    print("Prediction correct for run", run, "of permutation", permutation, "looking for", cid, ":",
                          prediction)
                    correct_predictions += 1
                else:
                    print("Prediction incorrect for run", run, "of permutation", permutation, "looking for", cid, ":",
                          prediction, "instead of", target)

            prediction_rate = correct_predictions / len(leech_targets_for_permutation)
            # get metadata by inspecting the first item
            first_item = message_items_for_permutation[0]
            metadata = {'tricklingDelay': first_item['tricklingDelay'],
                        'permutationIndex': first_item['permutationIndex'],
                        'bandwidthMB': first_item['bandwidthMB'],
                        'fileSize': first_item['fileSize'],
                        'latencyMS': first_item['latencyMS'], }
            # store metadata and prediction rate in map
            prediction_map[delay] = {'prediction_rate': prediction_rate, 'metadata': metadata}
            print("Prediction rate for delay", delay, "is:", correct_predictions, "/",
                  len(leech_targets_for_permutation), "=",
                  prediction_rate)

    print(prediction_map)
