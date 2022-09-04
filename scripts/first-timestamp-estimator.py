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


def find_global_info_file(results_dir):
    print("Looking for global info file in {}".format(results_dir))
    for subdir, _, files in os.walk(results_dir):
        for filename in files:
            filepath = subdir + os.sep + filename
            if filepath.split("/")[-1] == "globalInfo.out":
                return filepath
    raise Exception("Could not find globalInfo.out file")


def process_info_line(l):
    l = json.loads(l)
    item = {'source': l['id'], 'timestamp': l['timestamp'], 'value': l['info'], 'type': l['type']}
    return item


def process_message_line(l):
    l = json.loads(l)
    item = l
    return item


class FirstTimestampEstimator:
    def __init__(self, messages):
        self.messages = messages

    def predict(self, run_num, cid):
        # filter messages related to target run
        run_messages = [m for m in self.messages if m['run'] == run_num]
        # filter messages related to target cid
        cid_messages = [m for m in run_messages if cid in m['message']['wants']]
        cid_messages.sort(key=lambda x: x['timestamp'])
        prediction = cid_messages[0]['peer']
        return prediction


if __name__ == "__main__":
    args = parse_args()

    results_dir = dir_path + '/results'
    if args.dir:
        results_dir = args.dir
    elif args.rel_dir:
        results_dir = dir_path + '/' + args.rel_dir

    info_file = find_global_info_file(results_dir)
    if args.source:
        info_file = args.source

    info_items = []
    with open(info_file, 'r') as f:
        for l in f.readlines():
            info_items.append(process_info_line(l))

    node_info_items = [item for item in info_items if item['type'] == 'node_info']
    leech_target_items = [item for item in info_items if item['type'] == 'leech_target']

    eavesdropper_nodes = [item['value'] for item in node_info_items if item['value']['node_type'] == 'Eavesdropper']

    # message history files of the eavesdropper nodes
    message_history_files = [str(node['directory']) + '/messageHistory.out' for node in eavesdropper_nodes]
    message_items = []
    for message_history_file in message_history_files:
        with open(message_history_file, 'r') as f:
            for l in f.readlines():
                message_items.append(process_message_line(l))

    estimator = FirstTimestampEstimator(message_items)

    correct_predictions = 0
    for leech_target in leech_target_items:
        run = leech_target['value']['run']
        cid = leech_target['value']['looking_for']
        # the prediction estimated by the estimator
        prediction = estimator.predict(run, cid)
        # the leech that should be identified by the estimator
        target = leech_target['value']['peer']

        if prediction == target:
            print("Prediction correct for run", run, "looking for", cid, ":", prediction)
            correct_predictions += 1

    prediction_rate = correct_predictions / len(leech_target_items)
    print("Prediction rate:", prediction_rate)
