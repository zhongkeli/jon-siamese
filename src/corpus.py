import pandas as pd
import tensorflow as tf
from utils import preprocess_sentence
from data import Data
from random import shuffle
import numpy as np
from utils import build_vocabulary, write_tfrecord
from os.path import join, isdir
from os import makedirs
import csv
import pickle

class Corpus:
    def __init__(self, corpus_name, path, preprocess=None):
        """ Load the data set in a class

        Arguments:
        :param preprocess: None if not pre-process will be applied
                           -1 if all sentences will be pre-processed
                           N sentences longer than N will be pre-processed
        """
        self._sim_data = []
        self._non_sim_data = []

        if corpus_name == 'ibm':
            self.load_ibm(path, preprocess)
        if corpus_name == 'quora':
            self.load_quora(path, preprocess)

    @property
    def sim_data(self):
        return self._sim_data

    @property
    def non_sim_data(self):
        return self._non_sim_data


    def save_data(self, preprocess, qid, q1, q2, label):
        if preprocess:
            q1 = preprocess_sentence(q1, preprocess)
            q2 = preprocess_sentence(q2, preprocess)
        # This is a non-duplicate sentence -> non similar
        if label == '0':
            self._non_sim_data.append(Data(qid, q1, q2, label, [0, 1]))
        # This is a duplicate sentence -> similar
        else:
            self._sim_data.append(Data(qid, q1, q2, label, [1, 0]))

    def load_ibm(self, path, preprocess):
        # TODO The ids of the IBM partitions with the ones released by Quora.
        with open(path) as dataset_file:
            for line in dataset_file:
                label, q1, q2, qid = line.strip().split('\t')
                self.save_data(preprocess, qid, q1, q2, label)

    def load_quora(self, path, preprocess):
        with open(path) as dataset_file:
            next(dataset_file)
            aux_line = ''
            for line in dataset_file:
                line_strip = line.strip().split('\t')
                # If some field is missing do not consider this entry.
                if len(line_strip) == 6:
                    qid, _, _, q1, q2, label = line.strip().split('\t')
                    self.save_data(preprocess, qid, q1, q2, label)

                else:
                    aux_line += line
                    strip_aux = aux_line.strip().split('\t')
                    if len(strip_aux) == 6:
                        qid, _, _, q1, q2, label = aux_line.strip().split('\t')
                        aux_line = ''
                        self.save_data(preprocess, qid, q1, q2, label)

    def shuffle(self):
        shuffle(self._sim_data)
        shuffle(self._non_sim_data)

    def to_index_data(self, data, vocab_processor):
        data.sentence_1 = np.array(list(vocab_processor.transform([data.sentence_1])))[0]
        data.sentence_2 = np.array(list(vocab_processor.transform([data.sentence_2])))[0]
        return data

    def write_partitions_mixed(self, partitions_path, one_hot=False):
        """ Create the partitions and write them in csv """
        # Shuffle the dataset
        # This was commented because the pipeline handles the shuffle.
        # self.shuffle()

        # Create and save the vocabularies
        vocab_non_sim = self._non_sim_data[:231027]
        vocab_sim = self._non_sim_data[:133263]
        vocab_processor, sequence_length = build_vocabulary(vocab_sim,
                                                            vocab_non_sim)
        if not isdir(partitions_path):
            makedirs(partitions_path)

        pickle.dump(vocab_processor, open(join(partitions_path, "vocab.train"), "wb"))
        pickle.dump(sequence_length, open(join(partitions_path, "sequence.len"), "wb"))

        # Create and save the  TRAIN FILE
        writer = tf.python_io.TFRecordWriter(join(partitions_path, "train.tfrecords"))
        lines = 0
        for i in range(133263):
            # Write a non similar sentence
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)

            # Write a similar sentence
            data = self._sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 2

        for i in range(133263, 231027):
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 1
        print("Saved {} data examples for training".format(lines))

        # Create and save the  DEV FILE
        writer = tf.python_io.TFRecordWriter(join(partitions_path, "dev.tfrecords"))
        lines = 0
        # Mixed part: similar and non similar sentences
        for i, j in zip(range(231027, 239027), range(133263, 141263)):
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)

            data = self._sim_data[j]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 2

        for i in range(239027, 243027):
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 1
        print("Saved {} data examples for development".format(lines))

        # Create and save the  TEST FILE
        writer = tf.python_io.TFRecordWriter(join(partitions_path, "test.tfrecords"))
        lines = 0
        # Mixed part: similar and non similar sentences
        for i, j in zip(range(243027, 251027), range(141263, 149263)):
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)

            data = self._sim_data[j]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 2

        for i in range(251027, 255027):
            data = self._non_sim_data[i]
            data_idx = self.to_index_data(data, vocab_processor)
            write_tfrecord(writer, data_idx, one_hot)
            lines += 1
        print("Saved {} data examples for testing".format(lines))

    def make_partitions_quora(self):
        self.shuffle()
        vocab_non_sim = self._non_sim_data[:231027]
        vocab_sim = self._non_sim_data[:133263]
        vocab_processor, sequence_length = build_vocabulary(vocab_sim,
                                                            vocab_non_sim)
        train_non_sim = [self.to_index_data(data, vocab_processor)
                         for data in self._non_sim_data[:207026]]
        train_sim = [self.to_index_data(data, vocab_processor)
                     for data in self._sim_data[:117262]]
        dev_non_sim = [self.to_index_data(data, vocab_processor)
                       for data in self._non_sim_data[207027:231027]]
        dev_sim = [self.to_index_data(data, vocab_processor)
                   for data in self._sim_data[117263:133263]]
        test_non_sim = [self.to_index_data(data, vocab_processor)
                        for data in self._non_sim_data[231027:]]
        test_sim = [self.to_index_data(data, vocab_processor)
                    for data in self._sim_data[133263:]]

        return train_non_sim, train_sim, dev_non_sim, dev_sim, \
               test_non_sim, test_sim, vocab_processor, sequence_length

    def to_index(self, vocab_processor):
        for data in self.non_sim_data:
            data.sentence_1 = np.array(list(vocab_processor.transform([data.sentence_1])))[0]
            data.sentence_2 = np.array(list(vocab_processor.transform([data.sentence_2])))[0]
        for data in self.sim_data:
            data.sentence_1 = np.array(list(vocab_processor.transform([data.sentence_1])))[0]
            data.sentence_2 = np.array(list(vocab_processor.transform([data.sentence_2])))[0]