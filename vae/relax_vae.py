#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from tensorflow.examples.tutorials.mnist import input_data
import os
import cPickle


slim=tf.contrib.slim
Bernoulli = tf.contrib.distributions.Bernoulli
RelaxedOneHotCategorical = tf.contrib.distributions.RelaxedOneHotCategorical
Categorical = tf.contrib.distributions.Categorical



#%%
directory = os.getcwd()+'/discrete_out/'
if not os.path.exists(directory):
    os.makedirs(directory)
np_lr = 0.0001        
EXPERIMENT = 'RELAX'

batch_size = 200

training_epochs = 1000

tau0=1.0 

K=10
N=20

b_dim = N * K
x_dim = 784

straight_through=True 
learn_temp = True


def lrelu(x, alpha=0.1):
    return tf.nn.relu(x) - alpha * tf.nn.relu(-x)



def encoder(x,b_dim,reuse=False):
    with tf.variable_scope("encoder", reuse = reuse):
        h2 = slim.stack(x, slim.fully_connected,[256,512],activation_fn=lrelu)
        log_alpha = tf.layers.dense(h2, b_dim, activation=None)
    return log_alpha


def decoder(b,x_dim,reuse=False):
    #return logits
    with tf.variable_scope("decoder", reuse = reuse):
        h2 = slim.stack(b ,slim.fully_connected,[512, 256],activation_fn=lrelu)
        log_alpha = tf.layers.dense(h2, x_dim, activation=None)
    return log_alpha

def cv(b,reuse=False):
    #return control_variates
    with tf.variable_scope("control_var", reuse = reuse):
        h2 = slim.stack(b ,slim.fully_connected,[200, 200])
        out = tf.layers.dense(h2, 1, activation=None)
    return out

def kl_cat(q_logit, p_logit):
    '''
    input: N*n_cv*n_class
    '''
    eps = 1e-5
    q = tf.nn.softmax(q_logit,dim=2)
    p = tf.nn.softmax(p_logit,dim=2)
    return tf.reduce_sum(q*(tf.log(q+eps)-tf.log(p+eps)),axis = [1,2])


def bernoulli_loglikelihood(b, log_alpha):
    return b * (-tf.nn.softplus(-log_alpha)) + (1 - b) * (-log_alpha - tf.nn.softplus(-log_alpha))



def fun(x_star,E,logits_y,reuse_decoder=False):
    '''
    x_star is N*d_x, E is N* (n_cv*n_class), z_concate is N*n_cv*n_class
    prior_logit0 is n_cv*n_class
    calculate log p(x_star|E) + log p(E) - log q(E|x_star)
    x_star is observe x; E is latent b
    return (N,)
    '''

    logits_py = tf.ones_like(logits_y) * 1./K #uniform
    # (bs)
    KL = kl_cat(logits_y, logits_py) 
    
    #log p(x_star|E)
    logit_x = decoder(E,x_dim,reuse=reuse_decoder)
    log_p_x_given_b = bernoulli_loglikelihood(x_star, logit_x)
    # (N,)
    log_p_x_given_b = tf.reduce_sum(log_p_x_given_b, axis=-1)
    
    neg_elbo = - log_p_x_given_b + KL
    
    return neg_elbo

#%%


tf.reset_default_graph() 

eps = 1e-8

lr=tf.constant(0.0001)


x0 = tf.placeholder(tf.float32, shape=(batch_size,784), name='x')
x = tf.to_float(x0 > .5)

logits_y_ = encoder(x,b_dim)
logits_y = tf.reshape(logits_y_,[-1,N,K])

q_y = Categorical(logits=logits_y)

y_sample = q_y.sample() #N*n_cv
y_sample = tf.one_hot(y_sample,depth=K)  #N*n_cv*n_class
y_sample = tf.cast(y_sample,tf.float32)


y_flat = slim.flatten(y_sample)



neg_elbo = fun(x, y_flat, logits_y)
loss = tf.reduce_mean(neg_elbo)

gen_opt = tf.train.AdamOptimizer(lr)
gen_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='decoder')
gen_gradvars = gen_opt.compute_gradients(loss, var_list=gen_vars)
gen_train_op = gen_opt.apply_gradients(gen_gradvars)

###############################
#given Categorical logits_y, use RELAX to compute gradient to the logits

u1 = tf.random_uniform(shape = [N,K])
u1 = u1[None,:]
u2 = tf.random_uniform(shape = [N,K])
u2 = u2[None,:]
theta = tf.nn.softmax(logits_y, dim=-1) #bs*N*K
z = tf.log(theta + eps) - tf.log(-tf.log(u1 + eps) + eps)
b = tf.argmax(z, axis=-1)

b_onehot0 = tf.one_hot(b,depth=K)
b_onehot = b_onehot0 * (-1)
b_onehot = b_onehot + 1 # make everywhere 1 except for i = b is 0
b_flat = tf.cast(slim.flatten(b_onehot0),tf.float32)

tmp = -b_onehot * tf.log(u2 + eps) / theta
z_tilde = -tf.log(tmp - tf.log(u2+eps))
#bs
logp = tf.reduce_sum(tf.log(tf.reduce_sum(b_onehot0*theta,-1)+eps),-1)

z_flat = slim.flatten(z)
z_tilde_flat = slim.flatten(z_tilde)
#bs
F = fun(x,b_flat,logits_y,reuse_decoder=True) #to minimize

cv_z = tf.squeeze(cv(z_flat))
cv_z_tilde = tf.squeeze(cv(z_tilde_flat, reuse=True))

inf_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='encoder')

relax_loss = tf.reduce_mean(tf.stop_gradient(F - cv_z_tilde)*logp - cv_z_tilde + cv_z)
alpha_grads = tf.gradients(relax_loss, logits_y_)
inf_grads = tf.gradients(logits_y_, inf_vars, grad_ys=alpha_grads)


inf_opt = tf.train.AdamOptimizer(lr)
inf_gradvars = zip(inf_grads, inf_vars)
inf_train_op = inf_opt.apply_gradients(inf_gradvars)


###############################
vectorized_grads = tf.concat(
      [tf.reshape(g, [-1]) for g in inf_grads if g is not None], axis=0)
#vectorized_grads = tf.reshape(alpha_grads, [-1])

cv_loss = tf.reduce_mean(tf.square(vectorized_grads))
cv_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='control_var')
cv_train_op = tf.train.AdamOptimizer(lr).minimize(cv_loss, var_list = cv_vars)

###############################

with tf.control_dependencies([gen_train_op, inf_train_op, cv_train_op]):
    train_op = tf.no_op()



init_op=tf.global_variables_initializer()


#%% TRAIN
# get data
mnist = input_data.read_data_sets(os.getcwd()+'/MNIST', one_hot=True)
train_data = mnist.train
test_data = mnist.test
valid_data = mnist.validation


total_points = mnist.train.num_examples
total_batch = int(total_points / batch_size)
total_test_batch = int(mnist.test.num_examples / batch_size)
total_valid_batch = int(mnist.validation.num_examples / batch_size)

display_step = total_batch

#%%
def get_loss(sess,data,total_batch):
    cost_eval = []                  
    for j in range(total_batch):
        xs, _ = data.next_batch(batch_size)  
        cost_eval.append(sess.run(neg_elbo,{x:xs}))
    return np.mean(cost_eval)

if __name__ == "__main__": 
    print('Training starts....',EXPERIMENT)
    
    sess=tf.InteractiveSession()
    sess.run(init_op)
    record = [];step = 0
       
    import time
    start = time.time()
    COUNT=[]; COST=[]; TIME=[];COST_TEST=[];COST_VALID=[];epoch_list=[];time_list=[]
    evidence_r = []
    
    for epoch in range(training_epochs):
        
        record = [];
        
        for i in range(total_batch):
            train_xs,_ = train_data.next_batch(batch_size)   
            _,cost = sess.run([train_op,loss],{x:train_xs,lr:np_lr})
            record.append(cost)
            step += 1
            #print(cost)
        
        print(epoch,'cost=',np.mean(record),'with std=',np.std(record))
        
        if epoch%1 == 0:
            COUNT.append(step); COST.append(np.mean(record)); TIME.append(time.time()-start)
            COST_VALID.append(get_loss(sess,valid_data,total_valid_batch))
        if epoch%5 == 0:
            epoch_list.append(epoch)
            time_list.append(time.time()-start)
            all_ = [COUNT,COST,TIME,COST_TEST,COST_VALID,epoch_list,time_list,evidence_r]
            cPickle.dump(all_, open(directory+EXPERIMENT, 'wb'))
                
    
    print(EXPERIMENT)












