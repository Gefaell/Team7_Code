from typing import Tuple
from core import RAWFILES, load_file
import pandas as pd
#from sklearn.model_selection import train_test_split as _train_test_split
import numpy as np
from sklearn import metrics
import matplotlib.pyplot as plt

from bayes_opt import BayesianOptimization
from bayes_opt import UtilityFunction
from bayes_opt.logger import JSONLogger
from bayes_opt.event import Events
from bayes_opt.util import load_logs

import os, time

BASE_NAMES = [name for name in load_file(RAWFILES.SIGNAL)]

def ml_strip_columns(dataframe,
    accepted_column_names: Tuple[str, ...]=(),
    reject_column_names: Tuple[str, ...]=()
) -> pd.DataFrame:
    """Strips columns which contain information we don't want to pass to the ML model"""

    dataframe = dataframe.copy()

    # Drops 'year' and 'B0_ID' columns
    columns_names_to_drop = ('year','B0_ID')

    # Drops any columns added during processing not specified to keep
    for name in dataframe:
        if (
            not (name in BASE_NAMES or name in accepted_column_names or name == 'category')
            or name in reject_column_names or name in columns_names_to_drop
        ):
            dataframe.drop(name, inplace=True, axis=1)

    return dataframe

def ml_train_model(training_data, model, **kwargs):
    """Trains a ML model. Requires that the parameter `training_data` contains a column named 'category'
    which will be the value the ML model is trained to predict; this should contain only integers,
    preferably only 0 or 1.
    """

    train_vars = training_data.drop('category',axis=1)
    model.fit(train_vars.values, training_data['category'].to_numpy().astype('int'), **kwargs)
    return model

def _train_test_split(dataset, test_size, random_state = 1):
    dataset_reorder = dataset.sample(frac=1, axis=0, random_state = random_state)
    dataset_reorder = dataset_reorder.reset_index(drop=True)
    m = int ((1-test_size) * len(dataset_reorder))
    return dataset_reorder[0:m], dataset_reorder[m:]

def ml_prepare_train_test(dataset, randomiser_seed = 1) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Takes a dataset and splits it into test and train datasets"""
    # Marek
    train, test = _train_test_split(dataset, test_size = 0.2, random_state=randomiser_seed)
    return train, test

def ml_prepare_train_validate_test(dataset, randomiser_seed_a = 1, randomiser_seed_b = 2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    train_validate, test = ml_prepare_train_test(dataset, randomiser_seed = randomiser_seed_a)
    train, validate = ml_prepare_train_test(train_validate, randomiser_seed = randomiser_seed_b)
    return train, validate, test


def ml_combine_signal_bk(signal_dataset, background_dataset):
    """Combines signal and background dataset, adding category labels
    """
    # Marek
    signal_dataset = signal_dataset.copy()
    background_dataset = background_dataset.copy()
    signal_dataset.loc[:,'category'] = 1
    background_dataset.loc[:,'category'] = 0

    dataset = pd.DataFrame(
        np.concatenate((background_dataset.values, signal_dataset.values), axis = 0),
        columns = [name for name in signal_dataset]
    )
    dataset = dataset.reset_index(drop=True)
    dataset_reorder = dataset.sample(frac=1, axis=0)
    dataset_reorder = dataset_reorder.reset_index(drop=True)
    return dataset_reorder

def ml_get_model_sig_prob(testData, model):
    if 'category' in testData:
        test_vars = testData.drop('category',axis=1)
    else:
        test_vars = testData
    return model.predict_proba(test_vars.values)[:,1]

def test_false_true_negative_positive(test_dataset, sig_prob, threshold) -> dict:
    # Jiayang

    x = test_dataset['category'].to_numpy()

    x_mask_0 = x == 0
    x_mask_1 = x == 1
    prb_mask_pos = sig_prob >= threshold
    prb_mask_neg = sig_prob < threshold

    signal = np.count_nonzero(x_mask_1)
    background = np.count_nonzero(x_mask_0)
    true_positive =  np.count_nonzero(np.logical_and(x_mask_1, prb_mask_pos))
    false_negative = np.count_nonzero(np.logical_and(x_mask_1, prb_mask_neg))
    false_positive = np.count_nonzero(np.logical_and(x_mask_0, prb_mask_pos))
    true_negative =  np.count_nonzero(np.logical_and(x_mask_0, prb_mask_neg))
    
    # rates
    tpr = true_positive / signal
    fpr = false_positive / background

    fnr = false_negative / signal
    tnr = true_negative / background

    return {
        'true-positive': tpr,
        'false-positive': fpr,
        'true-negative': tnr,
        'false-negative': fnr,
        'signal': signal,
        'background': background,
        'n-signal-accept': signal * tpr,
        'n-background-accept': background * fpr,
    }


def roc_curve(model, test_data):
    # Jose
    '''
    Test data needs to be in pandas dataframe format.
    Implement the following model before this function:
        model = XGBClassifier()
        model.fit(training_data[training_columns], training_data['category'])
        sp = model.predict_proba(test_data[training_columns])[:,1]
        model.predict_proba(test_data[training_columns])
    This returns an array of N_samples by N_classes.
    The first column is the probability that the candiate is category 0 (background).
    The second column (sp) is the probability that the candidate is category 1 (signal).

    The Receiver Operating Characteristic curve given by this function shows the efficiency of the classifier
    on signal (true positive rate, tpr) against the inefficiency of removing background (false positive
    rate, fpr). Each point on this curve corresponds to a cut value threshold.
    '''

    sp = ml_get_model_sig_prob(test_data, model)
    fpr, tpr, cut_values = metrics.roc_curve(test_data['category'], sp)
    area = metrics.auc(fpr, tpr)

    return {
        'fpr': fpr,
        'tpr': tpr,
        'cut_values': cut_values,
        'area': area
    }

def plot_roc_curve(fpr, tpr, area):
    # Jose

    plt.plot([0, 1], [0, 1], color='deepskyblue', linestyle='--', label='Random guess')
    plt.plot(fpr, tpr, color='darkblue', label=f'ROC curve (area = {area:.2f})')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.legend(loc='lower right')
    plt.gca().set_aspect('equal', adjustable='box')
    #plt.show()

def test_sb(test_dataset, sig_prob, threshold):
    # Jiayang

    output = test_false_true_negative_positive(test_dataset, sig_prob, threshold)

    S = output['signal'] * output['true-positive']
    B = output['background'] * output['false-positive']
    metric = S/np.sqrt(S+B)

    return metric


def bayesian_nextpoint(function, pbounds, random_state=1, **util_args):
    """
    Suggestion:
        Not to use this, but use the bayesian_optimisation function below.
        bc it does not perform optimisation continuously.

    input:
        random_state: int, default = 1
            can be an integer for consistent outputs, or None for random outputs

        util_args: dict
            tweak this (or random_state) to get different params each time,
            for example, util_args = {'kind':"ucb", 'kappa':2.5,'xi':0.0}

    output:
        next_point : dict
            a set of params within pbounds, for example: {'x': 123, 'y': 123}
    """
    optimizer = BayesianOptimization(function, pbounds, verbose=2, random_state=random_state)

    utility = UtilityFunction(**util_args)
    next_point = optimizer.suggest(utility)
    print("next_point:", next_point)

    return next_point

def bayesian_optimisation(function, 
    pbounds, log_folder, bool_load_logs = True, explore_runs = 2, exploit_runs = 1):
    """
    runs function to find optimal parameters

    output:
        result : dict
            for example, {'target': 123, 'params': {'x': 123, 'y': 123}}
            where target = function(params)
    """
    print('====== start bayesian optimisation ======')
    
    optimizer = BayesianOptimization(function, pbounds, verbose=2, random_state=1,)
    if bool_load_logs:
        log_folder_files = os.listdir(log_folder)
        logs=[
            os.path.join(log_folder, f) for f in log_folder_files if (
                f[0:5] == 'logs_' and f[-5:] == '.json'
            )
        ]
        load_logs(optimizer, logs=logs)
    timestr = time.strftime("%Y%m%d-%H%M%S")
    logger = JSONLogger(path=os.path.join(log_folder, f'logs_{timestr}'))
    optimizer.subscribe(Events.OPTIMIZATION_STEP, logger)
    if exploit_runs > 0 or exploit_runs > 0:
        optimizer.maximize(init_points = explore_runs, n_iter = exploit_runs,)
    print('====== end bayesian optimisation ======')

    return optimizer
