import os

dir_path = os.path.dirname(os.path.realpath(__file__))


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


def get_prediction_rate(messages, targets):
    """
    Calculate the prediction rate for a given set of messages and the targets containing info about the true source
    :param messages: The messages to use for prediction
    :param targets: The targets containing info about the true source
    :return: The prediction rate
    """
    estimator = FirstTimestampEstimator(messages)
    correct_predictions = 0
    for target in targets:
        prediction = estimator.predict(target['permutationIndex'], target['run'], target['lookingFor'])
        target['prediction'] = prediction
        target['prediction_correct'] = prediction == target['peer']

        if target['prediction_correct']:
            correct_predictions += 1

    # Return the prediction rate
    return correct_predictions / len(targets)
