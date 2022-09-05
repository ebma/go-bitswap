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

    def predict(self, permutation_index, run_num, cid):
        # filter messages related to target permutation and run
        run_messages = [m for m in self.messages if
                        m['permutationIndex'] == str(permutation_index) and m['run'] == str(run_num)]
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

    estimator = FirstTimestampEstimator(eavesdropper_message_items)

    correct_predictions = 0
    for leech_target in leech_target_items:
        permutation = leech_target['value']['permutationIndex']
        run = leech_target['value']['run']
        cid = leech_target['value']['lookingFor']
        # the prediction estimated by the estimator
        prediction = estimator.predict(permutation, run, cid)
        # the leech that should be identified by the estimator
        target = leech_target['value']['peer']

        if prediction == target:
            print("Prediction correct for run", run, "of permutation", permutation, "looking for", cid, ":", prediction)
            correct_predictions += 1
        else:
            print("Prediction incorrect for run", run, "looking for", cid, ":", prediction, "instead of", target)

    prediction_rate = correct_predictions / len(leech_target_items)
    print("Prediction rate:", prediction_rate)
