#!/usr/bin/Python
# -*- coding: utf-8 -*-
import os
import sys
import csv
import math
import numpy as np
import tensorflow as tf

# 将运行路径切换到当前文件所在路径
cur_dir_path = os.path.abspath(os.path.split(__file__)[0])
if cur_dir_path:
    os.chdir(cur_dir_path)
    sys.path.append(cur_dir_path)
    sys.path.append(os.path.split(cur_dir_path)[0])

import bi_load as load
import lib.base as base
import model.vgg as vgg

''' 
 全卷积神经网络 
 该方法将 30 分类 转化为 30 个 二分类问题，需要训练 30 个网络，最后根据各个网络的准确率作为权重，加权投票作为输出
 
 优点：
    可扩展性，当新增分类时，无需重新训练全部数据，只需针对新分类训练一个新的网络即可
    
 致命缺点：
    尽管单个网络的准确率能高达 90+%，但当需要整合 30 个网络时，能保证不出错的概率就变成 0.9 ^ 30 = 0.0424 ，这是
    一个非常小的数字，意味着当综合考虑时，总会有一些网络会出错出现干扰，导致准确率无法提升
 
'''


class VGG16(base.NN):
    MODEL_NAME = 'bi_vgg_16'  # 模型的名称

    ''' 参数的配置 '''

    BATCH_SIZE = 16  # 迭代的 epoch 次数
    EPOCH_TIMES = 80  # 随机梯度下降的 batch 大小

    NUM_CHANNEL = 3  # 输入图片为 3 通道，彩色
    NUM_CLASSES = 2  # 输出的类别

    NUM_PIG = 30

    # early stop
    MAX_VAL_ACCURACY_DECR_TIMES = 15  # 校验集 val_accuracy 连续 100 次没有降低，则 early stop

    # 数据集的配置
    TRAIN_DATA_RATIO = 0.01  # 训练集占数据量的百分比
    VAL_DATA_END_RATIO = 0.02  # 校验集 + 训练集 占数据量的百分比

    # 学习率的相关参数
    BASE_LEARNING_RATE = [0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00003, 0.00005, 0.00005, 0.00005,
                          0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005,
                          0.00005, 0.00005, 0.00005, 0.00005, 0.00001, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005]

    DECAY_RATE = [0.0001, 0.0001, 0.00005, 0.00006, 0.00006, 0.00006, 0.00005, 0.00005, 0.0001, 0.0001,
                  0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.00006, 0.0001,
                  0.0001, 0.0001, 0.00007, 0.0001, 0.00005, 0.0001, 0.0001, 0.0001, 0.00008, 0.00008]

    # 防止 overfitting 相关参数
    REGULAR_BETA = [0.1, 0.1, 0.3, 0.1, 0.1, 0.1, 0.03, 0.2, 0.15, 0.2,
                    0.1, 0.1, 0.01, 0.1, 0.1, 0.15, 0.1, 0.03, 0.03, 0.01,
                    0.1, 0.1, 0.01, 0.03, 0.02, 0.3, 0.5, 0.2, 0.01, 0.04]  # 正则化的 beta 参数
    KEEP_PROB = 0.5  # dropout 的 keep_prob

    # 学习率的相关参数
    BASE_LEARNING_RATE_1 = [0.0000005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.00005,
                            0.00005, 0.00005, 0.00005,
                            0.00005, 0.00005, 0.00005, 0.00005, 0.00005, 0.0001, 0.00005,
                            0.00005, 0.00005, 0.00000005,
                            0.00005, 0.00005, 0.00000005, 0.00005, 0.00005, 0.00005, 0.00005,
                            0.00005, 0.00005, 0.00005]

    DECAY_RATE_1 = [0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001,
                    0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001,
                    0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.00005, 0.00005]

    # 防止 overfitting 相关参数
    REGULAR_BETA_1 = [0.01, 0.01, 0.3, 0.01, 0.01, 0.01, 0.03, 0.2, 0.15, 0.2,
                      0.01, 0.01, 0.1, 0.01, 0.01, 0.15, 0.01, 0.03, 0.03, 0.01,
                      0.01, 0.01, 0.01, 0.03, 0.02, 0.3, 0.5, 0.2, 0.01, 0.04]  # 正则化的 beta 参数

    # 保存模型时 校验集准确率 与 训练集准确率的占比: accuracy = val_accuracy * VAL_WEIGHT + train_accuracy * (1 - VAL_WEIGHT)
    VAL_WEIGHT = 0.7

    ACCURACY_OVER_95 = [0, 19, 22]  # 准确率超过 95% 的网络
    # 30个网络分别的权重
    NET_WEIGHT = [
        0.972826,  # net 0
        0.904762,  # net 1
        0.591146,  # net 2
        0.899740,  # net 3
        0.880319,  # net 4
        0.805990,  # net 5
        0.709635,  # net 6
        0.772135,  # net 7
        0.845052,  # net 8
        0.861979,  # net 9
        0.860677,  # net 10
        0.807292,  # net 11
        0.940104,  # net 12
        0.797965,  # net 13
        0.894531,  # net 14
        0.803191,  # net 15
        0.819010,  # net 16
        0.889323,  # net 17
        0.909896,  # net 18
        0.959239,  # net 19
        0.847826,  # net 20
        0.921875,  # net 21
        0.960938,  # net 22
        0.886719,  # net 23
        0.500000,  # net 24
        0.593750,  # net 25
        0.638021,  # net 26
        0.641927,  # net 27
        0.929167,  # net 28
        0.864583,  # net 29
    ]
    # 30 个网络按等级划分
    OPTION_LIST = [
        [0, 19, 22],
        [1, 3, 4, 9, 10, 12, 14, 17, 21, 23, 28, 29],
        [5, 7, 8, 11, 13, 15, 16, 18, 20],
        [6, 26, 27],
        [2, 24, 25]
    ]

    CORRECT_WEIGHT = [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9,
                      0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9,
                      0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    INCORRECT_WEIGHT = [1.3, 1.3, 1.1, 1.3, 1.3, 1.3, 1.3, 1.2, 1.3, 1.3,
                        1.1, 1.3, 1.2, 1.3, 1.3, 1.3, 1.3, 1.2, 1.3, 1.3,
                        1.3, 1.3, 1.2, 1.3, 1.3, 1.3, 1.3, 1.2, 1.3, 1.3]

    ''' 类的配置 '''

    USE_MULTI = True
    USE_BN = True  # 网络里是否使用了 batch normalize
    USE_BN_INPUT = True  # 输入是否使用 batch normalize

    SHOW_PROGRESS_FREQUENCY = 2  # 每 SHOW_PROGRESS_FREQUENCY 个 step show 一次进度 progress

    RESULT_DIR = r'result'
    RESULT_FILE_PATH = r'result/test_B.csv'

    ''' 模型的配置；采用了 VGG16 模型的 FCN '''

    LOSS_TYPE = 1  # loss type 有两种；0：使用正常的loss，1：使用log_loss

    IMAGE_SHAPE = [56, 56]
    IMAGE_PH_SHAPE = [None, IMAGE_SHAPE[0], IMAGE_SHAPE[1], NUM_CHANNEL]  # image 的 placeholder 的 shape

    VGG_MODEL = vgg.VGG.load()  # 加载 VGG 模型

    MODEL = [
        {
            'name': 'conv1_1',
            'type': 'conv',
            'W': VGG_MODEL['conv1_1'][0],
            'b': VGG_MODEL['conv1_1'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv1_2',
            'type': 'conv',
            'W': VGG_MODEL['conv1_2'][0],
            'b': VGG_MODEL['conv1_2'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'pool_1',
            'type': 'pool',
            'k_size': 2,
            'pool_type': 'avg',
        },
        {
            'name': 'conv2_1',
            'type': 'conv',
            'W': VGG_MODEL['conv2_1'][0],
            'b': VGG_MODEL['conv2_1'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv2_2',
            'type': 'conv',
            'W': VGG_MODEL['conv2_2'][0],
            'b': VGG_MODEL['conv2_2'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'pool_2',
            'type': 'pool',
            'k_size': 2,
            'pool_type': 'avg',
        },
        {
            'name': 'conv3_1',
            'type': 'conv',
            'W': VGG_MODEL['conv3_1'][0],
            'b': VGG_MODEL['conv3_1'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv3_2',
            'type': 'conv',
            'W': VGG_MODEL['conv3_2'][0],
            'b': VGG_MODEL['conv3_2'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv3_3',
            'type': 'conv',
            'W': VGG_MODEL['conv3_3'][0],
            'b': VGG_MODEL['conv3_3'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'pool_3',
            'type': 'pool',
            'k_size': 2,
            'pool_type': 'avg',
        },
        {
            'name': 'conv4_1',
            'type': 'conv',
            'W': VGG_MODEL['conv4_1'][0],
            'b': VGG_MODEL['conv4_1'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv4_2',
            'type': 'conv',
            'W': VGG_MODEL['conv4_2'][0],
            'b': VGG_MODEL['conv4_2'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv4_3',
            'type': 'conv',
            'W': VGG_MODEL['conv4_3'][0],
            'b': VGG_MODEL['conv4_3'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'pool_4',
            'type': 'pool',
            'k_size': 2,
            'pool_type': 'avg',
        },
        {
            'name': 'conv5_1',
            'type': 'conv',
            'W': VGG_MODEL['conv5_1'][0],
            'b': VGG_MODEL['conv5_1'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv5_2',
            'type': 'conv',
            'W': VGG_MODEL['conv5_2'][0],
            'b': VGG_MODEL['conv5_2'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'conv5_3',
            'type': 'conv',
            'W': VGG_MODEL['conv5_3'][0],
            'b': VGG_MODEL['conv5_3'][1],
            'bn': USE_BN,
            'trainable': False,
        },
        {
            'name': 'pool_5',
            'type': 'pool',
            'k_size': 2,
            'pool_type': 'max',
        },
        {
            'name': 'fc6',
            'type': 'fc',
            'shape': [2048, 1024],
            'trainable': True,
        },
        {
            'name': 'dropout_6',
            'type': 'dropout',
        },
        {
            'name': 'fc7',
            'type': 'fc',
            'shape': [1024, 512],
            'trainable': True,
        },
        {
            'name': 'dropout_7',
            'type': 'dropout',
        },
        {
            'name': 'fc8',
            'type': 'fc',
            'shape': [512, 256],
            'trainable': True,
        },
        {
            'name': 'dropout_8',
            'type': 'dropout',
        },
        {
            'name': 'softmax',
            'type': 'fc',
            'shape': [256, NUM_CLASSES],
            'activate': False,
        },
    ]

    ''' 自定义 初始化变量 过程 '''

    def init(self):
        self.__train_set_list = [None for i in range(self.NUM_PIG)]
        self.__val_set_list = [None for i in range(self.NUM_PIG)]

        self.__train_size_list = [0 for i in range(self.NUM_PIG)]
        self.__val_size_list = [0 for i in range(self.NUM_PIG)]

    def reinit(self, net_id):
        self.net_id = net_id

        # 加载数据
        self.load()

        # 常量
        self.__iter_per_epoch = int(self.__train_size_list[self.net_id] // self.BATCH_SIZE)
        self.__steps = self.EPOCH_TIMES * self.__iter_per_epoch

        self.__has_rebuild = False

        # 输入 与 label
        self.__image = tf.placeholder(tf.float32, self.IMAGE_PH_SHAPE, name='X')
        self.__label = tf.placeholder(tf.float32, [None, self.NUM_CLASSES], name='y')
        self.__size = tf.placeholder(tf.float32, name='size')

        # dropout 的 keep_prob
        self.keep_prob = tf.placeholder(tf.float32, name='keep_prob')

        # tensor is_train，用于 batch_normalize; 没有用 bn 时，无需加入 feed_dict
        self.t_is_train = tf.placeholder(tf.bool, name='is_train')

        self.global_step = self.get_global_step()

        learning_rate = self.BASE_LEARNING_RATE[self.net_id] if self.LOSS_TYPE == 0 else \
            self.BASE_LEARNING_RATE_1[self.net_id]
        decay_rate = self.DECAY_RATE[self.net_id] if self.LOSS_TYPE == 0 else \
            self.DECAY_RATE_1[self.net_id]

        self.__learning_rate = self.get_learning_rate(
            learning_rate, self.global_step, self.__steps, decay_rate,
            staircase=False
        )

        self.sess = tf.Session(graph=self.graph)

    ''' 加载数据 '''

    def load(self):
        self.__train_set_list[self.net_id] = load.Data(self.net_id, 0.0, self.TRAIN_DATA_RATIO, 'train',
                                                       self.IMAGE_SHAPE)
        self.__val_set_list[self.net_id] = load.Data(self.net_id, self.TRAIN_DATA_RATIO, self.VAL_DATA_END_RATIO,
                                                     'validation',
                                                     self.IMAGE_SHAPE)

        self.__train_size_list[self.net_id] = self.__train_set_list[self.net_id].get_size()
        self.__val_size_list[self.net_id] = self.__val_set_list[self.net_id].get_size()

    ''' 模型 '''

    def model(self):
        if self.start_from_model:
            self.restore_model_w_b(self.start_from_model)
            self.rebuild_model()
        else:
            self.__output = self.parse_model(self.__image)

    ''' 重建模型 '''

    def rebuild_model(self):
        self.__output = self.parse_model_rebuild(self.__image)

    ''' 计算 loss '''

    def get_loss(self):
        with tf.name_scope('loss'):
            self.__loss = tf.reduce_mean(
                tf.nn.softmax_cross_entropy_with_logits(logits=self.__output, labels=self.__label)
            )

    ''' 将图片输出到 tensorboard '''

    def __summary(self):
        with tf.name_scope('summary'):
            self.__mean_accuracy = tf.placeholder(tf.float32, name='mean_accuracy')
            self.__mean_loss = tf.placeholder(tf.float32, name='mean_loss')
            self.__mean_log_loss = tf.placeholder(tf.float32, name='mean_log_loss')
            # self.__mean_ch_log_loss = tf.placeholder(tf.float32, name='mean_ch_log_loss')

            tf.summary.scalar('learning_rate', self.__learning_rate)
            tf.summary.scalar('mean_accuracy', self.__mean_accuracy)
            tf.summary.scalar('mean_loss', self.__mean_loss)
            tf.summary.scalar('mean_log_loss', self.__mean_log_loss)
            # tf.summary.scalar('mean_ch_log_loss', self.__mean_ch_log_loss)

    ''' 计算准确率 '''

    def __get_accuracy(self):
        with tf.name_scope('accuracy'):
            labels = tf.argmax(self.__label, 1)
            predict = tf.argmax(self.__output, 1)
            correct = tf.equal(labels, predict)  # 返回 predict 与 labels 相匹配的结果

            self.__accuracy = tf.divide(tf.reduce_sum(tf.cast(correct, tf.float32)), self.__size)  # 计算准确率

    ''' 计算 log_loss '''

    def __get_log_loss(self):
        with tf.name_scope('log_loss'):
            labels = self.__label
            predict = tf.one_hot(tf.argmax(self.__output, 1), depth=self.NUM_CLASSES)

            correct = tf.cast(tf.equal(labels, predict), tf.float32)
            incorrect = tf.cast(tf.not_equal(labels, predict), tf.float32)

            w = correct * self.CORRECT_WEIGHT[self.net_id] + incorrect * self.INCORRECT_WEIGHT[self.net_id]
            output = w * self.__output

            # if self.net_id in self.ACCURACY_OVER_95:
            #     self.__prob = predict
            # else:
            exp_x = tf.transpose(tf.exp(self.__output))
            self.__prob = tf.transpose(exp_x / tf.reduce_sum(exp_x, axis=0))
            self.__prob = tf.maximum(tf.minimum(self.__prob, 1 - 1e-15), 1e-15)
            self.__log_loss = - tf.divide(tf.reduce_sum(tf.multiply(self.__label, tf.log(self.__prob))), self.__size)

            exp_x = tf.exp(output)
            p = exp_x / tf.reduce_sum(exp_x, axis=0)
            self.__ch_log_loss = - tf.divide(tf.reduce_sum(tf.multiply(self.__label, tf.log(p))), self.__size)

    def __measure(self, data_set, max_times=None):
        times = int(math.ceil(float(data_set.get_size()) / self.BATCH_SIZE))
        if max_times:
            times = min(max_times, times)

        mean_accuracy = 0.0
        mean_loss = 0.0
        mean_log_loss = 0.0
        # mean_ch_log_loss = 0.0
        for i in range(times):
            batch_x, batch_y = data_set.next_batch(self.BATCH_SIZE)

            mean_x = self.multi_mean_x[self.net_id] if len(self.multi_mean_x) > self.net_id else 0.0
            std_x = self.multi_std_x[self.net_id] if len(self.multi_std_x) > self.net_id else 1.0

            batch_x = (batch_x - mean_x) / (std_x + self.EPSILON)
            feed_dict = {self.__image: batch_x, self.__label: batch_y,
                         self.__size: batch_y.shape[0], self.keep_prob: 1.0,
                         self.t_is_train: False}

            # loss, log_loss, ch_log_loss, accuracy = self.sess.run([self.__loss, self.__log_loss, self.__ch_log_loss, self.__accuracy], feed_dict)
            loss, log_loss, accuracy = self.sess.run([self.__loss, self.__log_loss, self.__accuracy], feed_dict)
            mean_loss += loss
            mean_log_loss += log_loss
            # mean_ch_log_loss += ch_log_loss
            mean_accuracy += accuracy

            del batch_x
            del batch_y

            progress = float(i + 1) / times * 100
            self.echo('\r >> measuring progress: %.2f%% | %d \t' % (progress, times), False)

        return mean_accuracy / times, mean_loss / times, mean_log_loss / times

    def __measure_prob(self, data_set):
        batch_size = 100
        times = int(math.ceil(float(data_set.get_size()) / batch_size))
        count = 0
        data_set.reset_cur_index()
        prob_list = []

        while True:
            batch_x, _ = data_set.next_batch(batch_size, False)
            if isinstance(batch_x, type(None)):
                break

            mean_x = self.multi_mean_x[self.net_id] if len(self.multi_mean_x) > self.net_id else 0.0
            std_x = self.multi_std_x[self.net_id] if len(self.multi_std_x) > self.net_id else 1.0

            batch_x = (batch_x - mean_x) / (std_x + self.EPSILON)
            feed_dict = {self.__image: batch_x, self.keep_prob: 1.0, self.t_is_train: False}

            prob = self.sess.run(self.__prob, feed_dict)
            prob_list.append(prob[:, 1])

            del batch_x

            count += 1
            progress = float(count) / times * 100
            self.echo('\r >> measuring progress: %.2f%% | %d \t' % (progress, times), False)

        return np.hstack(prob_list)

    ''' 主函数 '''

    def run_i(self, pig_id):
        self.echo('\nStart training %d net ... ' % pig_id)

        # self.get_summary_path(pig_id)
        self.reinit(pig_id)

        # 生成模型
        self.model()

        # 计算 loss
        self.get_loss()

        self.__get_log_loss()

        if self.LOSS_TYPE == 0:
            loss_regular = self.regularize_trainable(self.__loss, self.REGULAR_BETA[self.net_id])
        elif self.LOSS_TYPE == 1:
            loss_regular = self.regularize_trainable(self.__log_loss, self.REGULAR_BETA_1[self.net_id])
        else:
            loss_regular = self.regularize_trainable(self.__ch_log_loss, self.REGULAR_BETA_1[self.net_id])

        # 正则化
        # self.__ch_loss_regular = self.regularize_trainable(self.__ch_log_loss, self.REGULAR_BETA[pig_id])

        # 生成训练的 op
        train_op = self.get_train_op(loss_regular, self.__learning_rate, self.global_step)

        self.__get_accuracy()

        # # tensorboard 相关记录
        # self.__summary()

        # 初始化所有变量
        self.init_variables()

        # # TensorBoard merge summary
        # self.merge_summary()

        mean_train_loss = 0
        mean_train_log_loss = 0
        # mean_train_ch_log_loss = 0
        mean_train_accuracy = 0

        moment = 0.975
        self.__running_mean = None
        self.__running_std = None

        self.__train_set_list[self.net_id].start_thread()
        self.__val_set_list[self.net_id].start_thread()

        self.echo('\nnet: %d  epoch:' % self.net_id)

        mean_val_accuracy, mean_val_loss, mean_val_log_loss = self.__measure(self.__val_set_list[self.net_id])

        best_val_log_loss = mean_val_log_loss
        best_val_accuracy = mean_val_accuracy
        incr_val_log_loss_times = 0

        self.echo('net: %d best val_accuracy: %.6f  val_loss: %.6f  val_log_loss: %.6f  ' % (self.net_id,
                                                                                             mean_val_accuracy,
                                                                                             mean_val_loss,
                                                                                             mean_val_log_loss))

        if self.start_from_model:
            self.get_new_model()  # 将模型保存到新的 model

        self.save_model_w_b()

        for step in range(self.__steps):
            if step % self.SHOW_PROGRESS_FREQUENCY == 0:
                epoch_progress = float(step) % self.__iter_per_epoch / self.__iter_per_epoch * 100.0
                step_progress = float(step) / self.__steps * 100.0
                self.echo('\r step: %d (%d|%.2f%%) / %d|%.2f%% \t\t' % (step, self.__iter_per_epoch, epoch_progress,
                                                                        self.__steps, step_progress), False)

            batch_x, batch_y = self.__train_set_list[self.net_id].next_batch(self.BATCH_SIZE)

            reduce_axis = tuple(range(len(batch_x.shape) - 1))
            _mean = np.mean(batch_x, axis=reduce_axis)
            _std = np.std(batch_x, axis=reduce_axis)
            self.__running_mean = moment * self.__running_mean + (1 - moment) * _mean if not isinstance(
                self.__running_mean, type(None)) else _mean
            self.__running_std = moment * self.__running_std + (1 - moment) * _std if not isinstance(
                self.__running_std, type(None)) else _std
            batch_x = (batch_x - _mean) / (_std + self.EPSILON)

            feed_dict = {self.__image: batch_x, self.__label: batch_y, self.keep_prob: self.KEEP_PROB,
                         self.__size: batch_y.shape[0], self.t_is_train: True}

            _, train_loss, train_log_loss, train_accuracy = self.sess.run(
                [train_op, self.__loss, self.__log_loss, self.__accuracy], feed_dict)

            mean_train_accuracy += train_accuracy
            mean_train_loss += train_loss
            mean_train_log_loss += train_log_loss
            # mean_train_ch_log_loss += train_ch_log_loss

            if step % self.__iter_per_epoch == 0 and step != 0:
                epoch = int(step // self.__iter_per_epoch)
                self.assign_list(self.multi_mean_x, self.net_id, self.__running_mean, 0.0)
                self.assign_list(self.multi_std_x, self.net_id,
                                 self.__running_std * (self.BATCH_SIZE / float(self.BATCH_SIZE - 1)), 1.0)

                mean_train_accuracy /= self.__iter_per_epoch
                mean_train_loss /= self.__iter_per_epoch
                mean_train_log_loss /= self.__iter_per_epoch
                # mean_train_ch_log_loss /= self.__iter_per_epoch

                # self.echo('\n epoch: %d  train_loss: %.6f  log_loss:    train_accuracy: %.6f \t ' % (epoch, mean_train_loss, mean_train_accuracy))
                #
                # feed_dict[self.__mean_accuracy] = mean_train_accuracy
                # feed_dict[self.__mean_loss] = mean_train_loss
                # feed_dict[self.__mean_log_loss] = mean_train_log_loss
                # # # feed_dict[self.__mean_ch_log_loss] = mean_train_ch_log_loss
                # self.add_summary_train(feed_dict, epoch)

                del batch_x
                del batch_y

                # 测试 校验集 的 loss
                mean_val_accuracy, mean_val_loss, mean_val_log_loss = self.__measure(self.__val_set_list[self.net_id],
                                                                                     100)
                # batch_val_x, batch_val_y = self.__val_set_list[pig_id].next_batch(self.BATCH_SIZE)
                #
                # batch_val_x = (batch_val_x - self.mean_x) / (self.std_x + self.EPSILON)

                # feed_dict = {self.__mean_accuracy: mean_val_accuracy, self.__mean_loss: mean_val_loss,
                #              self.__mean_log_loss: mean_val_log_loss}
                # self.add_summary_val(feed_dict, epoch)

                # del batch_val_x
                # del batch_val_y

                echo_str = '\n\t net: %d  epoch: %d  train_loss: %.6f  train_log_loss: %.6f  train_accuracy: %.6f  ' \
                           'val_loss: %.6f val_log_loss: %.6f  val_accuracy: %.6f' % (pig_id, epoch, mean_train_loss,
                                                                                      mean_train_log_loss,
                                                                                      mean_train_accuracy,
                                                                                      mean_val_loss, mean_val_log_loss,
                                                                                      mean_val_accuracy)

                mean_train_accuracy = 0
                mean_train_loss = 0
                mean_train_log_loss = 0

                condition_yes = False
                if self.LOSS_TYPE == 0:
                    mean_accuracy = self.VAL_WEIGHT * mean_val_accuracy + (1 - self.VAL_WEIGHT) * mean_train_accuracy
                    if best_val_accuracy < mean_accuracy:
                        best_val_accuracy = mean_accuracy
                        condition_yes = True
                else:
                    mean_log_loss = self.VAL_WEIGHT * mean_val_log_loss + (1 - self.VAL_WEIGHT) * mean_train_log_loss
                    if best_val_log_loss > mean_log_loss:
                        best_val_log_loss = mean_log_loss
                        condition_yes = True

                if condition_yes:
                    incr_val_log_loss_times = 0

                    self.echo('%s  best  ' % echo_str, False)
                    self.save_model_w_b()

                else:
                    incr_val_log_loss_times += 1
                    self.echo('%s  incr_times: %d \n' % (echo_str, incr_val_log_loss_times), False)

                    if incr_val_log_loss_times > self.MAX_VAL_ACCURACY_DECR_TIMES:
                        break

            else:
                del batch_x
                del batch_y

        # self.close_summary()        # 关闭 TensorBoard

        # self.__test_set.start_thread()

        self.restore_model_w_b()  # 恢复模型
        self.rebuild_model()  # 重建模型
        self.get_loss()  # 重新 get loss
        self.__get_accuracy()
        self.__get_log_loss()

        self.init_variables()  # 重新初始化变量

        mean_train_accuracy, mean_train_loss, mean_train_log_loss = self.__measure(self.__train_set_list[self.net_id])
        mean_val_accuracy, mean_val_loss, mean_val_log_loss = self.__measure(self.__val_set_list[self.net_id])
        # mean_test_accuracy, mean_test_loss, mean_test_log_loss = self.__measure(self.__test_set)

        self.__result.append([self.net_id, mean_train_accuracy, mean_train_loss, mean_train_log_loss,
                              mean_val_accuracy, mean_val_loss, mean_val_log_loss])

        self.__train_set_list[self.net_id].stop()  # 关闭获取数据线程
        self.__val_set_list[self.net_id].stop()  # 关闭获取数据线程
        # self.__test_set.stop()  # 关闭获取数据线程

        self.echo('\nFinish training %d net ' % self.net_id)

        self.sess.close()

        if self.start_from_model:
            self.reset_old_model_path()  # 恢复原来的 model_path

            # self.kill_tensorboard_if_runing()

    def run(self):
        self.__result = []

        # only_net = [2, 6]

        for i in range(self.NUM_PIG):
            # if i not in only_net:
            #     continue

            self.graph = tf.Graph()
            with self.graph.as_default():
                self.run_i(i)

            self.__show_result()

    ''' 展示保存的结果到 cmd '''

    def __show_result(self):
        for ret in self.__result:
            pig_id, mean_train_accuracy, mean_train_loss, mean_train_log_loss, \
            mean_val_accuracy, mean_val_loss, mean_val_log_loss = ret
            self.echo('\n*************************************************')
            self.echo('net: %d  train_accuracy: %.6f  train_loss: %.6f  train_log_loss: %.6f  ' % (pig_id,
                                                                                                   mean_train_accuracy,
                                                                                                   mean_train_loss,
                                                                                                   mean_train_log_loss))
            self.echo('net: %d  val_accuracy: %.6f  val_loss: %.6f  val_log_loss: %.6f  ' % (pig_id,
                                                                                             mean_val_accuracy,
                                                                                             mean_val_loss,
                                                                                             mean_val_log_loss))
            self.echo('*********************************')

    ''' test 时需要进行的 softmax '''

    def __np_softmax(self, x):
        for j in range(x.shape[1]):
            classes = x[:, j]
            # 根据网络的权重加权，并取加权后概率最大的类别
            correct_index = int(np.argmax(classes * np.array(self.NET_WEIGHT)))

            # 将正确的那个概率的权重加大
            net_weight = self.NET_WEIGHT[correct_index]
            classes[correct_index] = classes[correct_index] / pow(1.0 - net_weight, 1.2) * net_weight
            x[:, j] = classes

        exp_x = np.exp(x)
        return exp_x / np.sum(exp_x, axis=0)

    ''' test 时需要计算的 log_loss '''

    @staticmethod
    def __np_log_loss(prob, label):
        prob = np.minimum(np.maximum(prob, 1e-15), 1 - 1e-15)
        return - np.sum(np.multiply(label, np.log(prob))) / float(label.shape[0])

    ''' test 时计算的 accuracy '''

    @staticmethod
    def __np_accuracy(prob, label):
        prob = np.argmax(prob, axis=1)
        label = np.argmax(label, axis=1)
        return np.cast['float32'](np.sum(np.equal(prob, label))) / float(label.shape[0])

    ''' 测试第 i 个网络 '''

    def __test_i(self, i):
        self.echo('\nTesting %d net ... ' % i)

        self.reinit(i)

        self.__train_set_list[self.net_id].start_thread()
        self.__val_set_list[self.net_id].start_thread()

        self.restore_model_w_b()

        self.rebuild_model()

        self.get_loss()

        self.__get_accuracy()

        self.__get_log_loss()

        self.init_variables()

        mean_train_accuracy, mean_train_loss, mean_train_log_loss = self.__measure(self.__train_set_list[self.net_id],
                                                                                   100)
        mean_val_accuracy, mean_val_loss, mean_val_log_loss = self.__measure(self.__val_set_list[self.net_id], 100)

        self.__result.append([self.net_id, mean_train_accuracy, mean_train_loss, mean_train_log_loss,
                              mean_val_accuracy, mean_val_loss, mean_val_log_loss])

        train_prob_list = self.__measure_prob(self.__train_data)
        val_prob_list = self.__measure_prob(self.__val_data)

        self.__train_prob_list.append(train_prob_list)
        self.__val_prob_list.append(val_prob_list)

        self.sess.close()

        self.__train_set_list[self.net_id].stop()
        self.__val_set_list[self.net_id].stop()

        self.echo('Finish testing ')

    ''' 测试 '''

    def test(self):
        self.__result = []

        self.__train_prob_list = []
        self.__val_prob_list = []

        self.__train_data = load.TestData(0.0, self.TRAIN_DATA_RATIO, 'train', self.IMAGE_SHAPE)
        self.__val_data = load.TestData(self.TRAIN_DATA_RATIO, self.VAL_DATA_END_RATIO, 'validation', self.IMAGE_SHAPE)

        self.echo('\nStart testing ... ')
        for i in range(self.NUM_PIG):
            self.echo('  testing %d net ... ' % i)

            self.graph = tf.Graph()
            with self.graph.as_default():
                self.__test_i(i)

            self.__show_result()

        self.echo('Finish testing ')

        self.__train_prob_list = np.vstack(self.__train_prob_list)
        self.__val_prob_list = np.vstack(self.__val_prob_list)

        self.__train_prob_list = self.__np_softmax(self.__train_prob_list).transpose()
        self.__val_prob_list = self.__np_softmax(self.__val_prob_list).transpose()

        train_label_list = self.__train_data.get_label_list()
        val_label_list = self.__val_data.get_label_list()

        train_accuracy = self.__np_accuracy(self.__train_prob_list, train_label_list)
        val_accuracy = self.__np_accuracy(self.__val_prob_list, val_label_list)

        train_log_loss = self.__np_log_loss(self.__train_prob_list, train_label_list)
        val_log_loss = self.__np_log_loss(self.__val_prob_list, val_label_list)

        self.echo('\n****************************************')
        self.echo('train_accuracy: %.6f train_log_loss: %.8f' % (train_accuracy, train_log_loss))
        self.echo('val_accuracy: %.6f val_log_loss: %.8f' % (val_accuracy, val_log_loss))


# o_vgg = VGG16(False, '2018_01_12_01_38_40')
# o_vgg.run()

o_vgg = VGG16(True, '2018_01_12_01_38_40')
o_vgg.test()
