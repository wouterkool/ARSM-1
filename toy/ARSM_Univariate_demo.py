#!/usr/bin/env python2
# -*- coding: utf-8 -*-

#large C = 1000; in paper C =30

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from matplotlib import pyplot as plt
import tensorflow as tf
import random
#%matplotlib qt

import warnings
warnings.filterwarnings('ignore')
slim=tf.contrib.slim


IterMax = 200
stepsize = 1
C= 1000
r= 1000
seedi = 5
tf.set_random_seed(seedi)
np.random.seed(seedi)
random.seed(seedi)

def fun(z,C,r):
    return .5+(z+1)/C/r
    
def softmax(phi):
    e_phi = np.exp(phi - np.max(phi))
    return e_phi / np.sum(e_phi)
    
def pseudo_action_swap_matrix(pi,phi):
    C=len(pi)
    RaceAllSwap = np.log(pi[:,np.newaxis])-phi[np.newaxis,:]
    Race = np.diag(RaceAllSwap)
    action_true = np.argmin(Race)
    Race_min = Race[action_true]
    
    if C<7: # True: #True:
        #Slow version for large C
        pseudo_actions=np.full((C, C), action_true)
        for m in range(C):
            for jj in  range(m):
                RaceSwap = Race.copy()
                RaceSwap[m], RaceSwap[jj]=RaceAllSwap[jj,m],RaceAllSwap[m,jj]
                s_action = np.argmin(RaceSwap)
                pseudo_actions[m,jj], pseudo_actions[jj,m] = s_action, s_action
    else:
        #Fast version for large C
        pseudo_actions=np.full((C, C), action_true)
        
        SwapSuccess = RaceAllSwap<=Race_min
        SwapSuccess[action_true,:]=True
        np.fill_diagonal(SwapSuccess,0)
        m_idx,j_idx = np.where(SwapSuccess)
        
        for i in range(len(m_idx)):
            m,jj = m_idx[i],j_idx[i]
            RaceSwap = Race.copy()
            RaceSwap[m], RaceSwap[jj] = RaceAllSwap[jj,m],RaceAllSwap[m,jj]
            if m==action_true or jj == action_true:
                s_action = np.argmin(RaceSwap)
                pseudo_actions[m,jj], pseudo_actions[jj,m] = s_action, s_action
            else:
                if RaceSwap[m]<RaceSwap[jj]:
                    pseudo_actions[m,jj], pseudo_actions[jj,m] = m, m
                else:
                    pseudo_actions[m,jj], pseudo_actions[jj,m] = jj, jj
        
    return pseudo_actions, action_true 

def pseudo_action_swap_vector(pi,phi,Cat_ref):
    C=len(pi)
    Race = np.log(pi)-phi
    action_true=np.argmin(Race)
    pseudo_actions=np.full(C, action_true)
    for m in range(C):
        jj=Cat_ref
        RaceSwap = Race.copy()
        if m!=jj:
            RaceSwap[m] = np.log(pi[jj])-phi[m]
            RaceSwap[jj] = np.log(pi[m])-phi[jj]
            pseudo_actions[m] = np.argmin(RaceSwap)
    return pseudo_actions


phi_init = np.zeros(C)
#phi_init = np.random.normal(0,1,C)
#phi_init = np.arange(C,0,-1)/C-0.5
#phi_init[0]=3

phi_true = phi_init.copy()
phi_true_record=[]
prob_true_record=[]
reward_expected_true_record=[]
grad_true_record=[]

phi_REINFORCE = phi_init.copy()
phi_REINFORCE_record=[]
prob_REINFORCE_record=[]
reward_expected_REINFORCE_record=[]
grad_REINFORCE_record=[]

phi_ar = phi_init.copy()
phi_ar_record=[]
prob_ar_record=[]
reward_expected_ar_record=[]
grad_ar_record=[]

phi_ars = phi_init.copy()
phi_ars_record=[]
prob_ars_record=[]
reward_expected_ars_record=[]
grad_ars_record=[]

phi_arsm = phi_init.copy()
phi_arsm_record=[]
prob_arsm_record=[]
reward_expected_arsm_record=[]
grad_arsm_record=[]


Fun = fun(np.arange(C),C,r)


sess=tf.InteractiveSession()
sess.run(tf.global_variables_initializer())    

phi_gs_record=[]
prob_gs_record=[]
grad_gs_record=[]
reward_expected_gs_record=[]
########################################

idx = []


VAR_reinforce = []
VAR_ar = []
VAR_ars = []
VAR_arsm = []
VAR_gumbel = []


snr_reinforce = []
snr_ar = []
snr_ars = []
snr_arsm = []
snr_gumbel = []

pseudo_prop = []
entropy = []
pseudo_prop2 = []

for iter in range(IterMax):

    pi =  np.random.dirichlet(np.ones(C))
    
    #########    
    #gradient ascent with true grad
    prob_true = softmax(phi_true)
    grad_true = prob_true*Fun - prob_true*np.sum(Fun*prob_true)
    
    phi_true = phi_true + stepsize * grad_true
    prob_true = softmax(phi_true)
    reward_expected_true = np.sum(prob_true*Fun)
    
    phi_true_record.append(phi_true)
    prob_true_record.append(prob_true)
    reward_expected_true_record.append(reward_expected_true)
    grad_true_record.append(grad_true)   
    
    
    #########
    #gradient ascent with REINFORCE
    action_true = np.argmin(np.log(pi)-phi_REINFORCE)
    prob_REINFROCE = softmax(phi_REINFORCE)
    onehot =np.zeros(C)
    onehot[action_true]=1
    grad_REINFORCE=Fun[action_true]*(onehot-prob_REINFROCE)
    
    phi_REINFORCE = phi_REINFORCE + stepsize * grad_REINFORCE
    prob_REINFORCE = softmax(phi_REINFORCE)
    reward_expected_REINFORCE = np.sum(prob_REINFORCE*Fun)
    
    phi_REINFORCE_record.append(phi_REINFORCE)
    prob_REINFORCE_record.append(prob_REINFORCE)
    reward_expected_REINFORCE_record.append(reward_expected_REINFORCE)
    grad_REINFORCE_record.append(grad_REINFORCE)  
    

    #########
    #gradient ascent with Augment-REINFORCE (AR) grad
    action_true = np.argmin(np.log(pi)-phi_ar)
    grad_ar=Fun[action_true]*(1-pi)
    phi_ar = phi_ar + stepsize * grad_ar
    prob_ar= softmax(phi_ar)
    reward_expected_ar = np.sum(prob_ar*Fun)
    
    phi_ar_record.append(prob_ar)
    prob_ar_record.append(prob_ar)
    reward_expected_ar_record.append(reward_expected_ar)
    grad_ar_record.append(grad_ar)  
    
    
    #########
    #gradient ascent with Augment-REINFORCE-Swap (ARS) grad
    Ref_cat=np.random.randint(C)
    pseudo_actions  = pseudo_action_swap_vector(pi,phi_ars,Ref_cat)  
    F=fun(pseudo_actions,C,r)
    grad_ars = (F-np.mean(F))*(1.0-C*pi[Ref_cat])
         
    phi_ars = phi_ars + stepsize * grad_ars
    prob_ars = softmax(phi_ars)
    reward_expected_ars = np.sum(prob_ars*Fun)
    
    phi_ars_record.append(prob_ars)
    prob_ars_record.append(prob_ars)
    reward_expected_ars_record.append(reward_expected_ars)
    grad_ars_record.append(grad_ars)  
    
    
    #########
    #gradient ascent with ARSM grad       
    pseudo_actions, true_action = pseudo_action_swap_matrix(pi,phi_arsm)    
    
    
    
    if True:
        #Slow version if evaluate function is expensive
        F=fun(pseudo_actions,C,r)   
    else:
        #Fast version if evaluating function is expensive
        unique_pseudo_actions = np.unique(pseudo_actions[pseudo_actions!=action_true])
        F = np.full((C,C),fun(action_true,C,r))
        for action in unique_pseudo_actions:
            F[pseudo_actions==action]=fun(action,C,r)
    meanF = np.mean(F,axis=0)
    #grad_arsm=np.transpose(np.matmul(F-meanF,1.0/C-pi[:,np.newaxis]))[0]
    grad_arsm = np.matmul(F-meanF,1.0/C-pi)   
    
    phi_arsm = phi_arsm + stepsize * grad_arsm
    prob_arsm = softmax(phi_arsm)
    reward_expected_arsm = np.sum(prob_arsm*Fun)
    
    phi_arsm_record.append(prob_arsm)
    prob_arsm_record.append(prob_arsm)
    reward_expected_arsm_record.append(reward_expected_arsm)
    grad_arsm_record.append(grad_arsm)  
    
    pseudo_prop.append(np.sum(pseudo_actions != true_action) / (C*(C-1)))
    entropy.append(np.sum(- prob_arsm*np.log(prob_arsm + 1e-10)))
    pseudo_prop2.append(len(np.unique(pseudo_actions)) / C)
    
    
    if iter%10 == 0:
        print("Iter: " + str(iter))
    
    if iter % 20 == 0:
        idx.append(iter)
        var_reinforce = []
        var_ar = []
        var_ars = []
        var_arsm = []
        var_gumbel = []
        for j in range(100):
            #piz = np.random.exponential(np.ones(C))
            #piz = piz/np.sum(piz)
            piz = np.random.dirichlet(np.ones(C))
            
            action_truez = np.argmin(np.log(piz)-phi_REINFORCE)
            onehotz =np.zeros(C)
            onehotz[action_truez]=1
            #prob_REINFROCE = softmax(phi_REINFORCE)
            grad_REINFORCEz=Fun[action_truez]*(onehotz-prob_REINFROCE)            
            var_reinforce.append(grad_REINFORCEz)
            
            
            action_truez = np.argmin(np.log(piz)-phi_ar)
            grad_arz=Fun[action_truez]*(1-piz)
            var_ar.append(grad_arz)
            
            Ref_catz=np.random.randint(C)
            pseudo_actionsz  = pseudo_action_swap_vector(piz,phi_ars,Ref_catz)  
            Fz=fun(pseudo_actionsz,C,r)
            grad_arsz = (Fz-np.mean(Fz))*(1.0-C*piz[Ref_catz])
            var_ars.append(grad_arsz)
            
            action_truez = np.argmin(np.log(piz)-phi_arsm)
            pseudo_actionsz, _= pseudo_action_swap_matrix(piz,phi_arsm) 
            Fz=fun(pseudo_actionsz,C,r) 
            meanFz = np.mean(Fz,axis=0)
            grad_arsmz = np.matmul(Fz-meanFz,1.0/C-piz) 
            var_arsm.append(grad_arsmz)

        VAR_reinforce.append(np.mean(np.var(var_reinforce,axis=0)))
        VAR_ar.append(np.mean(np.var(var_ar,axis=0)))
        VAR_ars.append(np.mean(np.var(var_ars,axis=0)))
        VAR_arsm.append(np.mean(np.var(var_arsm,axis=0)))
        
        
        mean = np.mean(var_reinforce,axis=0)
        std = np.std(var_reinforce,axis=0)
        snr_reinforce.append(np.abs(mean)/std)
        
        mean = np.mean(var_ar,axis=0)
        std = np.std(var_ar,axis=0)
        snr_ar.append(np.abs(mean)/std)
        
        mean = np.mean(var_ars,axis=0)
        std = np.std(var_ars,axis=0)
        snr_ars.append(np.abs(mean)/std)

        mean = np.mean(var_arsm,axis=0)
        std = np.std(var_arsm,axis=0)
        snr_arsm.append(np.abs(mean)/std)


#%%

f, [[ax11,ax12,ax13,ax14,ax15],[ax21,ax22,ax23,ax24,ax25], [ax31,ax32,ax33,ax34,ax35],\
    [ax41,ax42,ax43,ax44,ax45]] \
        = plt.subplots(4, 5,sharex=True,figsize=(12,6))    

ax11.set_title('True',fontsize='x-large')
ax12.set_title('REINFORCE',fontsize='x-large')
ax13.set_title('AR',fontsize='x-large')
ax14.set_title('ARS',fontsize='x-large')
ax15.set_title('ARSM',fontsize='x-large')

    
ax11.plot(reward_expected_true_record,label = 'True');
ax12.plot(reward_expected_REINFORCE_record, label = 'REINFORCE');
ax13.plot(reward_expected_ar_record, label = 'AR');
ax14.plot(reward_expected_ars_record, label = 'ARS');
ax15.plot(reward_expected_arsm_record, label = 'ARSM');
ax11.set_ylabel('Reward',fontsize='x-large') 



ax21.plot(np.vstack(grad_true_record)[:,(0,-1)],label = 'True',alpha=1); 
ax22.plot(np.vstack(grad_REINFORCE_record)[:,(0,-1)], label = 'REINFORCE',alpha=0.3);
ax23.plot(np.vstack(grad_ar_record)[:,(0,-1)], label = 'AR',alpha=0.3);
ax24.plot(np.vstack(grad_ars_record)[:,(0,-1)], label = 'ARS',alpha=0.3);
ax25.plot(np.vstack(grad_arsm_record)[:,(0,-1)], label = 'ARSM',alpha=0.3);
ax21.set_ylabel('Gradient',fontsize='x-large') 



ax31.semilogy(np.vstack(prob_true_record)[:,(0,-1)],label = 'True'); 
ax32.semilogy(np.vstack(prob_REINFORCE_record)[:,(0,-1)], label = 'REINFORCE');
ax33.semilogy(np.vstack(prob_ar_record)[:,(0,-1)], label = 'AR');
ax34.semilogy(np.vstack(prob_ars_record)[:,(0,-1)], label = 'ARS');
ax35.semilogy(np.vstack(prob_arsm_record)[:,(0,-1)], label = 'ARSM');
ax31.set_ylabel('Probability',fontsize='x-large')

ax41.plot(idx,np.array(VAR_reinforce)*0,label = 'True');
ax42.plot(idx,VAR_reinforce, label = 'REINFORCE');
ax43.plot(idx,VAR_ar, label = 'AR');
ax44.plot(idx,VAR_ars, label = 'ARS');
ax45.plot(idx,VAR_arsm, label = 'ARSM');
ax41.set_ylabel('Grad_var',fontsize='x-large') 


plt.tight_layout(w_pad=0.02, h_pad=0.01)
plt.subplots_adjust(wspace=0.35, hspace=0.2)
f.text(0.5, 0.004, 'Iteration', ha='center',fontsize='x-large')

l1 = np.min(reward_expected_arsm_record); r1 = np.max(reward_expected_arsm_record);
ax11.set_ylim([l1,r1])
ax12.set_ylim([l1,r1])
ax13.set_ylim([l1,r1])
ax14.set_ylim([l1,r1])
ax15.set_ylim([l1,r1])


l3 = 0; r3 = 1;
ax31.set_ylim([l3,r3])
ax32.set_ylim([l3,r3])
ax33.set_ylim([l3,r3])
ax34.set_ylim([l3,r3])
ax35.set_ylim([l3,r3])


ax21.yaxis.get_major_formatter().set_powerlimits((0,3))

for ax in [ax41,ax42,ax43,ax44,ax45]:
    ax.yaxis.get_major_formatter().set_powerlimits((0,3))
for ax in [ax21,ax22,ax23,ax24,ax25]:
    ax.yaxis.get_major_formatter().set_powerlimits((0,2))


plt.tight_layout()






   
