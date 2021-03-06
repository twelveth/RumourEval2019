import json
import os
import sys; sys.path.insert(0, '../organizers_baseline/preprocessing')

import numpy as np
import pandas as pd

from tree2branches import tree2branches
from features import *


def load_subtask_targets(data_dir: str, subtask: str, train: bool):
    assert subtask in ['a', 'b'], 'subtask parameter should be a or b'

    targets_file = 'train-key.json' if train else 'dev-key.json'
    with open(os.path.join(data_dir, targets_file), 'r') as f:
        targets = json.load(f)
        subtask_targets = targets['subtask' + subtask + 'english']

    if subtask == 'a':
        sqdc_to_int = {'support': 0., 'deny': 1., 'query': 2., 'comment': 3.}
        for key, value in subtask_targets.items():
            subtask_targets[key] = sqdc_to_int[value]

    else:
        veracity_to_int = {'true': 0., 'false': 1., 'unverified': 2.}
        for key, value in subtask_targets.items():
            subtask_targets[key] = veracity_to_int[value]

    return pd.Series(subtask_targets)

def load_rumours_data(data_dir):
    struct_file = 'structure.json'
    data_struct = {}
    rumours_source_dict = {}
    rumours_replies_dict = {}

    for source_dir in next(os.walk(data_dir))[1]:
        if 'reddit' in source_dir:

            for rumour_dir in next(os.walk(os.path.join(data_dir, source_dir)))[1]:
                rumour_path = os.path.join(data_dir, source_dir, rumour_dir)
                with open(os.path.join(rumour_path, struct_file), 'r') as f:
                    data_struct.update(json.load(f))

                rsd, rrd = load_single_rumour_data(rumour_path, 'reddit')
                rumours_source_dict.update(rsd)
                rumours_replies_dict.update(rrd)

        else:

            for theme_dir in next(os.walk(os.path.join(data_dir, source_dir)))[1]:
                theme_path = os.path.join(data_dir, source_dir, theme_dir)
                for rumour_dir in next(os.walk(theme_path))[1]:
                    rumour_path = os.path.join(theme_path, rumour_dir)
                    with open(os.path.join(rumour_path, struct_file), 'r') as f:
                        data_struct.update(json.load(f))

                    rsd, rrd = load_single_rumour_data(rumour_path, 'twitter')
                    rumours_source_dict.update(rsd)
                    rumours_replies_dict.update(rrd)

    return rumours_source_dict, rumours_replies_dict, data_struct

def load_single_rumour_data(rumour_path, source):
    rumour_source_dict = {}
    rumour_replies_dict = {}

    for d in next(os.walk(rumour_path))[1]:
        if d in ['source-tweet', 'replies']:
            for rumour_file in os.listdir(os.path.join(rumour_path, d)):
                with open(os.path.join(rumour_path, d, rumour_file), 'r') as f:
                    rumour = json.load(f)
                    rumour_data = handle_rumour(rumour, d, source)
                    if d == 'source-tweet':
                        rumour_source_dict.update(rumour_data)
                    else:
                        rumour_replies_dict.update(rumour_data)
    return rumour_source_dict, rumour_replies_dict

def handle_rumour(rumour, directory, source):
    if directory == 'source-tweet':

        if source == 'reddit':
            rumour = rumour['data']['children'][0]['data']
            rumour_data = {rumour['id']:
                            {'text': text_preprocess(rumour['title'])}}
        else:
            rumour_data = {str(rumour['id']):
                            {'text': text_preprocess(rumour['text'])}}

    else:

        if source == 'reddit':
            rumour = rumour['data']
            try:
                rumour_data = {rumour['id']: {'text':
                                text_preprocess(rumour['body'])}}
            except KeyError:
                rumour_data = {rumour['id']: {'text': 'DELETED'}}

        else:
            rumour_data = {str(rumour['id']):
                            {'text': text_preprocess(rumour['text'])}}

    return rumour_data

def build_dataset(data_dir):
    rumours_source_dict, \
    rumours_replies_dict, \
    data_struct = load_rumours_data(data_dir)

    a_y_train = load_subtask_targets(data_dir, 'a', True)
    a_y_dev = load_subtask_targets(data_dir, 'a', False)
    b_y_train = load_subtask_targets(data_dir, 'b', True)
    b_y_dev = load_subtask_targets(data_dir, 'b', False)

    sources_df = pd.DataFrame.from_dict(rumours_source_dict, orient='index')
    replies_df = pd.DataFrame.from_dict(rumours_replies_dict, orient='index')

    a_train_data = pd.concat([replies_df, sources_df])
    a_train_data.drop(list(a_y_dev.keys()), inplace=True)
    a_train_data = a_train_data.assign(sqdc=a_y_train)

    a_dev_data = pd.concat([replies_df, sources_df])
    a_dev_data.drop(list(a_y_train.keys()), inplace=True)
    a_dev_data = a_dev_data.assign(sqdc=a_y_dev)

    b_train_data = sources_df.drop(list(b_y_dev.keys()))
    b_dev_data = sources_df.drop(list(b_y_train.keys()))

    b_train_data = add_features(b_train_data, a_train_data, data_struct)
    b_dev_data = add_features(b_dev_data, a_dev_data, data_struct)

    b_train_data = b_train_data.assign(veracity=b_y_train)
    b_dev_data = b_dev_data.assign(veracity=b_y_dev)

    return a_train_data, a_dev_data, \
            b_train_data, b_dev_data, data_struct

#--------------------------LINEAR------------------------------------

def lin_rumour_data(a_data, b_data, struct):
    X_dict = {}
    branches = tree2branches(struct)

    n_support = 0
    n_deny = 0
    n = 0

    for i, branch in enumerate(branches):
        n += len(branch[1:])

        for reply in branch[1:]:
            try:
                sqdc = a_data.loc[reply, 'sqdc']
            except KeyError:
                continue

            if sqdc == 'support':
                n_support += 1
            elif sqdc == 'deny':
                n_deny += 1

        try:
            veracity = b_data.loc[branch[0], 'veracity']
            X_dict.update({branch[0]: {'support': n_support / n, 'deny': n_deny / n, 'veracity': veracity}})
        except KeyError:
            pass

        if i < len(branches) - 1:
            if branches[i + 1][0] != branch[0]:
                n_support = 0
                n_deny = 0
                n = 0
    data = pd.DataFrame.from_dict(X_dict, orient='index')

    return data


def remove_unverified(data):
    data = data.loc[data.loc[:, 'veracity'].isin(['true', 'false'])]
    data.loc[:, 'veracity'] = [1 if v == 'true' else 0 for v in data.loc[:, 'veracity']]

    return data.loc[:, ['support', 'deny']], data.loc[:, 'veracity']
