# -*- coding: utf-8 -*-

import tensorflow as tf
import os

import common
from data_utils import Vocabulary
import numpy as np
from common import CheckpointLoader
from language_model import LM


class Model:
    def __init__(self, hps, logdir, datadir, mode='eval_'):
        with tf.variable_scope("model"):
            hps.num_sampled = 0
            hps.keep_prob = 1.0
            self.model = LM(hps, "eval", "/gpu:0")
        if hps.average_params:
            print("Averaging parameters for evaluation.")
            saver = tf.train.Saver(self.model.avg_dict)
        else:
            saver = tf.train.Saver()
        config = tf.ConfigProto(allow_soft_placement=True)
        self.sess = tf.Session(config=config)
        sw = tf.summary.FileWriter(logdir + "/" + mode, self.sess.graph)
        self.hps = hps
        self.num_steps = self.hps.num_steps
        vocab_path = os.path.join(datadir, "vocabulary.txt")
        with self.sess.as_default():
            success = common.load_from_checkpoint(saver, logdir + "/train")
        if not success:
            raise Exception('Loading Checkpoint failed')
        self.vocabulary = Vocabulary.from_file(vocab_path)

    # type of prefix_words is list
    def predictnextkwords(self, prefix_words, k):
        n = len(prefix_words) + 1
        x = np.zeros([self.hps.batch_size, self.hps.num_steps], dtype=np.int32)
        y = np.zeros([self.hps.batch_size, self.hps.num_steps], dtype=np.int32)
        x[0, :n] = ([self.vocabulary.s_id] +
                    list(map(self.vocabulary.get_id, prefix_words)))
        y[0, :n] = (list(map(self.vocabulary.get_id, prefix_words)) +
                    [self.vocabulary.s_id])
        prob = self.get_softmax_distrib(x, y, n)
        top_indices = self.argsort_k_largest(prob, k)
        return [(self.vocabulary.get_token(id_), prob[id_]) for id_ in top_indices]

    def argsort_k_largest(self, prob, k):
        if k >= len(prob):
            return np.argsort(prob)[::-1]
        indices = np.argpartition(prob, -k)[-k:]
        values = prob[indices]
        return indices[np.argsort(-values)]

    def get_softmax_distrib(self, x, y, n):
        print 'start'
        with self.sess.as_default():
            tf.local_variables_initializer().run()
            print 'Start predicting...'
            softmax = self.sess.run(self.model.softmax, {self.model.x: x, self.model.y: y})
            return softmax[n - 1]

    def getPPL(self, prefix_words):
        n = len(prefix_words) + 1
        x = np.zeros([self.hps.batch_size, self.hps.num_steps], dtype=np.int32)
        y = np.zeros([self.hps.batch_size, self.hps.num_steps], dtype=np.int32)
        x[0, :n] = ([self.vocabulary.s_id] +
                    list(map(self.vocabulary.get_id, prefix_words)))
        y[0, :n] = (list(map(self.vocabulary.get_id, prefix_words)) +
                    [self.vocabulary.s_id])
        with self.sess.as_default():
            tf.local_variables_initializer().run()
            ppl = self.sess.run(self.model.loss, {self.model.x: x, self.model.y: y})
            return [ppl, float(np.exp(ppl))]
