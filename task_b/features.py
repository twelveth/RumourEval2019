import sys; sys.path.insert(0, '../organizers_baseline/preprocessing')

import re
import pandas as pd
from nltk.tokenize import TweetTokenizer
from nltk.corpus import stopwords

from tree2branches import tree2branches


def text_preprocess(text):
    # tokenize
    tt = TweetTokenizer(preserve_case=False,
                        strip_handles=True,
                        reduce_len=True)
    tokens = [token for token in tt.tokenize(text)
                if not re.fullmatch(r'[\W_]+|rt|via', token)]

    # remove stopwords
    tokens = [token for token in tokens
                if token not in stopwords.words('english')]

    return tokens

def sqdc_percentage(stance_data, data_struct):
    sqdc_dict = {}
    branches = tree2branches(data_struct)

    n_support = 0
    n_deny = 0
    n_query = 0
    n = 0

    for i, branch in enumerate(branches):
        # if i == 0 or branch[0] == branches[i - 1][0]:
        #     n += len(branch[1:])
        # else:
        #     sqdc_dict.update({branches[i - 1][0]: {'support': n_support / n,
        #                                          'deny': n_deny / n,
        #                                          'query': n_query / n}})
        #     n_support = 0
        #     n_deny = 0
        #     n_query = 0
        #     n = len(branch[1:])
        n += len(branch[1:])

        for reply in branch[1:]:
            try:
                sqdc = stance_data.loc[reply, 'sqdc']
            except KeyError:
                continue

            if sqdc == 0:
                n_support += 1
            elif sqdc == 1:
                n_deny += 1
            elif sqdc == 2:
                n_query += 1

        if n != 0:
            if i != len(branches) - 1:
                if branch[0] != branches[i + 1][0]:
                    sqdc_dict.update({branch[0]: {'support': n_support / n,
                                                  'deny': n_deny / n,
                                                  'query': n_query / n}})
                    n_support = 0
                    n_deny = 0
                    n_query = 0
                    n = 0
            else:
                sqdc_dict.update({branch[0]: {'support': n_support / n,
                                              'deny': n_deny / n,
                                              'query': n_query / n}})

    data = pd.DataFrame.from_dict(sqdc_dict, orient='index')
    return data

def add_features(veracity_data, stance_data, data_struct):
    # sqd sqdc_percentage
    sqdc_data = sqdc_percentage(stance_data, data_struct)
    veracity_data = pd.concat([veracity_data, sqdc_data], axis=1, sort=False)

    return veracity_data
