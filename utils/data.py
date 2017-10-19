# Copyright 2017 Guanshuo Wang. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import os.path
import math
import threading

import numpy as np
import tensorflow as tf
from tensorflow.contrib.staging import StagingArea
from scipy import misc
from . import augment

NUM_ANGMENTATION_SUPPORT = 4

def get_image_paths_and_labels(list_path):
    image_paths_flat = []
    labels_flat = []
    with open(os.path.expanduser(list_path), 'r') as f:
      lines = f.readlines()
    for line in lines:
        part_line = line.split(' ')
        image_path = part_line[0]
        label_index = part_line[1]
        image_paths_flat.append(image_path)
        labels_flat.append(int(label_index))

    return image_paths_flat, labels_flat


def train_stage_inputs(data_list_path, 
                       batch_size, 
                       is_color, 
                       input_size, 
                       crop_size=None,
                       augment=False,
                       num_gpus=1,
                       num_preprocess_threads=None):
    num_channels = 3 if is_color else 1
    image_list, label_list = get_image_paths_and_labels(data_list_path)
    num_examples = len(label_list)
    num_classes = max(label_list)+1
    print('%d images loaded, totally %d classes' % (num_examples, num_classes))

    filename, label_index = tf.train.slice_input_producer([image_list, label_list], shuffle=True)

    images_and_labels = []
    for _ in range(num_preprocess_threads):
        file_contents = tf.read_file(filename)
        image = tf.image.decode_jpeg(file_contents, channels=num_channels)
        image = tf.image.convert_image_dtype(image, dtype=tf.float32)

        # Resize (crop_size is None.) or random crop (crop_size is given.)
        if crop_size is None:
            image = tf.image.resize_images(image, [input_size, input_size])
        else:
            image = tf.random_crop(image, [crop_size, crop_size, 3])
            input_size = crop_size

        # Data augmentation
        if augment:
            aug_num = np.random.randint(low=0, high=NUM_ANGMENTATION_SUPPORT)
            aug_queue = np.random.permutation(NUM_ANGMENTATION_SUPPORT)[0:aug_num]
            for aug_idx in aug_queue:
                if aug_idx == 0:
                    image = tf.image.random_flip_left_right(image)
                elif aug_idx == 1:
                    image = augment.random_zoom_in_out(image, min_rate=0.2)
                elif aug_idx == 2:
                    if num_channels == 1:
                        image = tf.image.random_brightness(image, 0.5)
                    elif num_channels == 3:
                        image = tf.image.random_hue(image, 0.25)
                elif aug_idx == 3:
                    if num_channels == 1:
                        image = tf.image.random_contrast(image, 0.2, 0.8)
                    elif num_channels == 3:
                        image = tf.image.random_saturation(image, 0.3, 0.8)
        else:
            image = tf.image.random_flip_left_right(image)

        image = tf.image.per_image_standardization(image)
        image.set_shape((input_size, input_size, num_channels))
        images_and_labels.append([image, label_index])

    raw_images, raw_labels = tf.train.batch_join(images_and_labels, batch_size=batch_size, 
                                                 capacity=2*num_preprocess_threads*batch_size,
                                                 allow_smaller_final_batch=True)

    tf.summary.image('images', image_batch, max_outputs=10)

    images = [[] for i in range(num_gpus)]
    labels = [[] for i in range(num_gpus)]
    raw_images = tf.unstack(raw_images, axis=0)
    raw_labels = tf.unstack(raw_labels, axis=0)

    for i in xrange(self.batch_size):
        split_index = i % num_gpus
        images[split_index].append(raw_images[i])
        labels[split_index].append(raw_labels[i])

    for split_index in xrange(num_gpus):
        images[split_index] = tf.parallel_stack(images[split_index])
        labels[split_index] = tf.parallel_stack(labels[split_index])

    image_producer_ops = []
    image_producer_stages = []
    images_shape = images[0].get_shape()
    labels_shape = labels[0].get_shape()
    for device_idx in xrange(num_gpus):
        image_producer_stages.append(StagingArea([images[0].dtype, labels[0].dtype], shapes=[images_shape, labels_shape]))
        put_op = image_producer_stages[device_idx].put(
                 [images[device_idx], labels[device_idx]])
        image_producer_ops.append(put_op)

    image_producer_ops = tf.group(*image_producer_ops)

    return image_producer_ops, image_producer_stages, num_classes, num_examples

def train_inputs(data_list_path, 
                 batch_size, 
                 is_color, 
                 input_size, 
                 crop_size=None,
                 augment=False,
                 num_preprocess_threads=None):
    num_channels = 3 if is_color else 1
    image_list, label_list = get_image_paths_and_labels(data_list_path)
    num_examples = len(label_list)
    num_classes = max(label_list)+1
    print('%d images loaded, totally %d classes' % (num_examples, num_classes))

    filename, label_index = tf.train.slice_input_producer([image_list, label_list], shuffle=True)

    images_and_labels = []
    for _ in range(num_preprocess_threads):
        file_contents = tf.read_file(filename)
        image = tf.image.decode_jpeg(file_contents, channels=num_channels)
        image = tf.image.convert_image_dtype(image, dtype=tf.float32)

        # Resize (crop_size is None.) or random crop (crop_size is given.)
        if crop_size is None:
            image = tf.image.resize_images(image, [input_size, input_size])
        else:
            image = tf.random_crop(image, [crop_size, crop_size, 3])
            input_size = crop_size

        # Data augmentation
        if augment:
            aug_num = np.random.randint(low=0, high=NUM_ANGMENTATION_SUPPORT)
            aug_queue = np.random.permutation(NUM_ANGMENTATION_SUPPORT)[0:aug_num]
            for aug_idx in aug_queue:
                if aug_idx == 0:
                    image = tf.image.random_flip_left_right(image)
                elif aug_idx == 1:
                    image = augment.random_zoom_in_out(image, min_rate=0.2)
                elif aug_idx == 2:
                    if num_channels == 1:
                        image = tf.image.random_brightness(image, 0.5)
                    elif num_channels == 3:
                        image = tf.image.random_hue(image, 0.25)
                elif aug_idx == 3:
                    if num_channels == 1:
                        image = tf.image.random_contrast(image, 0.2, 0.8)
                    elif num_channels == 3:
                        image = tf.image.random_saturation(image, 0.3, 0.8)
        else:
            image = tf.image.random_flip_left_right(image)

        image = tf.image.per_image_standardization(image)
        image.set_shape((input_size, input_size, num_channels))

        images_and_labels.append([image, label_index])

    image_batch, label_batch = tf.train.batch_join(images_and_labels, batch_size=batch_size, 
                                                   capacity=2*num_preprocess_threads*batch_size,
                                                   allow_smaller_final_batch=True)

    tf.summary.image('images', image_batch, max_outputs=10)
    
    return image_batch, label_batch, num_classes, num_examples

class ImageProducer(object):
    """An image producer that puts images into a staging area periodically.
    This class is useful for periodically running a set of ops, `put_ops` on a
    different thread every `batch_group_size` times.
    The notify_image_consumption() method is used to increment an internal counter
    so that when it is first called, `put_ops` is executed. Afterwards, every
    `batch_group_size` times notify_image_consumption() is called,
    `put_ops` is executed again. A barrier is placed so that the main thread is
    blocked until `put_ops` have been executed.
    The start() method is used to start the thread that runs `put_ops`.
    The done() method waits until the last put_ops is executed and stops the
    thread.
    The purpose of this class is to fill an image input pipeline every
    `batch_group_size` steps. Suppose `put_ops` supplies M images to the input
    pipeline when run, and that every step, (M/`batch_group_size`) images are
    consumed. Then, by calling notify_image_consumption() every step, images are
    supplied to the input pipeline at the same amount they are consumed.
    """

    def __init__(self, sess, put_ops, batch_group_size=1):
        self.sess = sess
        self.num_gets = 0
        self.put_ops = put_ops
        self.batch_group_size = batch_group_size
        self.done_event = threading.Event()
        self.put_barrier = Barrier(2)

    def _should_put(self):
        return self.num_gets % self.batch_group_size == 0

    def done(self):
        """Stop the image producer."""
        self.done_event.set()
        self.put_barrier.abort()
        self.thread.join()

    def start(self):
        """Start the image producer."""
        self.thread = threading.Thread(target=self._loop_producer)
        # Set daemon to true to allow Ctrl + C to terminate all threads.
        self.thread.daemon = True
        self.thread.start()

    def notify_image_consumption(self):
        """Increment the counter of image_producer by 1.
        This should only be called by the main thread that consumes images and runs
        the model computation.
        """
        if self._should_put():
            self.put_barrier.wait()
        self.num_gets += 1

    def _loop_producer(self):
        while not self.done_event.isSet():
            self.sess.run([self.put_ops])
            self.put_barrier.wait()

