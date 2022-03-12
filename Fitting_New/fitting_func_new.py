#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar  9 16:29:35 2022

@author: emirsezik
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from iminuit import Minuit
from modifiedselectioncuts import selection_all
from ml_selector import remove_combinatorial_background
from find_acceptance_new import acceptance_function

def binning(dataframe):
    q_start = [0.1, 1.1, 2.5, 4, 6, 15, 17, 11, 1, 15]
    q_end = [0.98, 2.5, 4, 6, 8, 17, 19, 12.5, 6, 17.9]
    bins = []
    q2 = dataframe["q2"]
    for i in range(len(q_start)):
        cond = (q2 >= q_start[i]) & (q2 <= q_end[i])
        bins.append(dataframe[cond])
    return bins
   
coeff = np.load('../tmp/coeff.npy')

#%% fist run to generate the files
dataframe = pd.read_pickle("Data/total_dataset.pkl")
dataframe,_  = selection_all(dataframe)
dataframe,_ = remove_combinatorial_background(dataframe)
np.save('../tmp/filtered_total_dataset.pkl', dataframe)

#%% read file to avoid recalculation
dataframe = pd.read_pickle('../tmp/filtered_total_dataset.pkl')

#%%
bins = binning(dataframe)

#%%
def decay_rate_S(F_l, A_fb, S_3, S_4, S_5, S_7, S_8, S_9, acceptance, q2, ctl, ctk, phi):
    """
    Returns the pdf defined above
    :param fl: f_l observable
    :param afb: a_fb observable
    :param cos_theta_l: cos(theta_l)
    :return:
    """
    stl = np.sqrt(1 - np.square(ctl))
    stk = np.sqrt(1 - np.square(ctk))
    c2tl = 2 * np.square(ctl) - 1
    s2tk = 2 * stk * ctk
    s2tl = 2 * stl * ctl
    stl_sq = np.square(stl)
    stk_sq = np.square(stk)
    
    scalar_array = 9 * np.pi / 32 * acceptance(q2, ctl, ctk, phi, coeff) * (3/4 * (1 - F_l) * stk_sq +
                                                  F_l * np.square(ctk) +
                                                  1/4 * (1 - F_l) * stk_sq * c2tl - 
                                                  F_l * np.square(ctk) * c2tl + 
                                                  S_3 * stk_sq * stl_sq * np.cos(2 * phi) +
                                                  S_4 * s2tk * s2tl * np.cos(phi) + 
                                                  S_5 * s2tk * stl * np.cos(phi) + 
                                                  4/3 * A_fb * stk_sq * ctl +
                                                  S_7 * s2tk * stl * np.sin(phi) +
                                                  S_8 * s2tk * s2tl * np.sin(phi) +
                                                  S_9 * stk_sq * stl_sq * np.sin(2 * phi)
                                                  )
    return scalar_array


def log_likelihood_S(F_l, A_fb, S_3, S_4, S_5, S_7, S_8, S_9, _bin):
    """
    Returns the negative log-likelihood of the pdf defined above
    :param fl: f_l observable
    :param afb: a_fb observable
    :param _bin: number of the bin to fit
    :return:
    """
    
    _bin = bins[int(_bin)]
    ctl = _bin['costhetal']
    ctk = _bin["costhetak"]
    phi = _bin["phi"]
    q2 = _bin["q2"]
    normalised_scalar_array = decay_rate_S(F_l, A_fb, S_3, S_4, S_5, S_7, S_8, S_9, acceptance_function, q2, ctl, ctk, phi)
    normalised_scalar_array = np.array([float(i) for i in normalised_scalar_array])

    return -np.sum(np.log(normalised_scalar_array))

#%%
log_likelihood_S.errordef = Minuit.LIKELIHOOD

results = []
errors = []

#%%
starting_point = [0.711290, 0.122155, -0.024751, -0.224204, -0.337140, -0.013383,-0.005062,-0.000706]
m = Minuit(log_likelihood_S, starting_point[0], starting_point[1], starting_point[2], 
               starting_point[3], starting_point[4], starting_point[5], 
               starting_point[6], starting_point[7], 1)
    
m.fixed['_bin'] = True  # fixing the bin number as we don't want to optimize it
m.limits=((-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0),
              (-1.0, 1.0), (-1.0, 1.0), None)
m.migrad()
results.append(np.array(m.values))
errors.append(np.array(m.errors))
#m.fmin
#m.params
