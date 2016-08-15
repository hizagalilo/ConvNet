from Dataset import Dataset
import os
import sys
import tensorflow as tf
import numpy as np
import logging as log
import time

IMG_SIZE = 224
IMAGE_DIR = os.getcwd() + '/small_dataset'
dataset = Dataset(IMAGE_DIR)
imgs_labels = dataset.getDataset()
# measuring time for getDataset()
timeit.timeit(dataset.getDataset(), setup="gc.enable()", number=10000)

log.info("getDataset time = ", (end - start))

# Parameters of Logistic Regression
BATCH_SIZE = 20
# learning_rate = 0.001
# max_epochs = 10
# display_step = 10
# std_dev = 1.0  # This affects accuracy

# Network Parameters
n_input = IMG_SIZE**2
n_classes = 4 
n_channels = 3
dropout = 0.8 # Dropout, probability to keep units


class ConvNet(object):

    # Constructor
    def __init__(self, learning_rate, max_epochs, display_step, std_dev):

        # Initialize params
        self.learning_rate=learning_rate
        self.max_epochs=max_epochs
        self.display_step=display_step
        self.std_dev=std_dev
        
        # Store layers weight & bias
        self.weights = {
            'wc1': tf.Variable(tf.random_normal([11, 11, 3, 96], stddev=std_dev)),
            'wc2': tf.Variable(tf.random_normal([5, 5, 96, 192], stddev=std_dev)),
            'wc3': tf.Variable(tf.random_normal([3, 3, 192, 384], stddev=std_dev)),
            'wc4': tf.Variable(tf.random_normal([3, 3, 384, 384], stddev=std_dev)),
            'wc5': tf.Variable(tf.random_normal([3, 3, 384, 256], stddev=std_dev)),
            
            'wd': tf.Variable(tf.random_normal([12544, 4096])),
            'wfc': tf.Variable(tf.random_normal([4096, 1024], stddev=std_dev)),
            
            'out': tf.Variable(tf.random_normal([1024, n_classes], stddev=std_dev))
        }
        
        self.biases = {
            'bc1': tf.Variable(tf.random_normal([96])),
            'bc2': tf.Variable(tf.random_normal([192])),
            'bc3': tf.Variable(tf.random_normal([384])),
            'bc4': tf.Variable(tf.random_normal([384])),
            'bc5': tf.Variable(tf.random_normal([256])),
            
            'bd': tf.Variable(tf.random_normal([4096])),
            'bfc': tf.Variable(tf.random_normal([1024])),

            'out': tf.Variable(tf.random_normal([n_classes]))
        }

        # Graph input
        self.img_pl = tf.placeholder(tf.float32, [None, n_input, n_channels])
        self.label_pl = tf.placeholder(tf.float32, [None, n_classes])
        self.keep_prob = tf.placeholder(tf.float32) # dropout (keep probability)
        
        # Create a saver for writing training checkpoints.
        self.saver = tf.train.Saver()

    # Return the next batch of size batch_size
    def nextBatch(self, imgs, labels, step, batch_size):
        s = step*batch_size
        return imgs[s:s+batch_size], labels[s:s+batch_size]

    """ 
    Create AlexNet model 
    """
    def conv2d(self, name, l_input, w, b, s):
        return tf.nn.relu(tf.nn.bias_add(tf.nn.conv2d(l_input, w, strides=[1, s, s, 1], padding='SAME'), b), name=name)

    def max_pool(self, name, l_input, k, s):
        return tf.nn.max_pool(l_input, ksize=[1, k, k, 1], strides=[1, s, s, 1], padding='SAME', name=name)

    def norm(self, name, l_input, lsize):
        return tf.nn.lrn(l_input, lsize, bias=2.0, alpha=0.001 / 9.0, beta=0.75, name=name)

    def alex_net_model(self, _X, _weights, _biases, _dropout):
        # Reshape input picture
        _X = tf.reshape(_X, shape=[-1, IMG_SIZE, IMG_SIZE, 3])

        # Convolution Layer 1
        conv1 = self.conv2d('conv1', _X, _weights['wc1'], _biases['bc1'], 4)
        # log.info("conv1.shape: ", conv1.get_shape())
        # Max Pooling (down-sampling)
        pool1 = self.max_pool('pool1', conv1, k=3, s=2)
        # log.info("pool1.shape:", pool1.get_shape())
        # Apply Normalization
        norm1 = self.norm('norm1', pool1, lsize=4)
        # log.info("norm1.shape:", norm1.get_shape())
        # Apply Dropout
        dropout1 = tf.nn.dropout(norm1, _dropout)    

        # Convolution Layer 2
        conv2 = self.conv2d('conv2', dropout1, _weights['wc2'], _biases['bc2'], s=1)
        # log.info("conv2.shape:", conv2.get_shape())
        # Max Pooling (down-sampling)
        pool2 = self.max_pool('pool2', conv2, k=3, s=2)
        # log.info("pool2.shape:", pool2.get_shape())
        # Apply Normalization
        norm2 = self.norm('norm2', pool2, lsize=4)
        # log.info("norm2.shape:", norm2.get_shape())
        # Apply Dropout
        dropout2 = tf.nn.dropout(norm2, _dropout)
        # log.info("dropout2.shape:", dropout2.get_shape())

        # Convolution Layer 3
        conv3 = self.conv2d('conv3', dropout2, _weights['wc3'], _biases['bc3'], s=1)
        # log.info("conv3.shape:", conv3.get_shape())

        # Convolution Layer 4
        conv4 = self.conv2d('conv4', conv3, _weights['wc4'], _biases['bc4'], s=1)
        # log.info("conv4.shape:", conv4.get_shape())

        # Convolution Layer 5
        conv5 = self.conv2d('conv5', conv4, _weights['wc5'], _biases['bc5'], s=1)
        # log.info("conv5.shape:", conv5.get_shape())
        pool5 = self.max_pool('pool5', conv5, k=3, s=2)
        # log.info("pool5.shape:", pool5.get_shape())

        # Fully connected layer 1
        pool5_shape = pool5.get_shape().as_list()
        dense = tf.reshape(pool5, [-1, pool5_shape[1] * pool5_shape[2] * pool5_shape[3]])
        # log.info("dense.shape:", dense.get_shape())
        fc1 = tf.nn.relu(tf.matmul(dense, _weights['wd']) + _biases['bd'], name='fc1')  # Relu activation
        # log.info("fc1.shape:", fc1.get_shape())
        
        # Fully connected layer 2
        fc2 = tf.nn.relu(tf.matmul(fc1, _weights['wfc']) + _biases['bfc'], name='fc2')  # Relu activation
        # log.info("fc2.shape:", fc2.get_shape())

        # Output, class prediction
        out = tf.matmul(fc2, _weights['out']) + _biases['out']

        # log.info("out.shape:", out.get_shape())
        # print("OUT = ", out)
        
        return out

    # Method for training the model and testing its accuracy
    def training(self):

        # Construct model
        pred = self.alex_net_model(self.img_pl, self.weights, self.biases, self.keep_prob)

# TO check # Define loss and optimizer
# http://stackoverflow.com/questions/33922937/why-does-tensorflow-return-nan-nan-instead-of-probabilities-from-a-csv-file
        cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(pred, self.label_pl))
        optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(cost)

        # Evaluate model
        correct_pred = tf.equal(tf.argmax(pred,1), tf.argmax(self.label_pl,1))
        accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

        # Initializing the variables
        init = tf.initialize_all_variables()

        # count total number of imgs
        img_count = dataset.getNumImages()

        # Launch the graph
        with tf.Session() as sess:
            sess.run(init)
            summary_writer = tf.train.SummaryWriter('/tmp/tf_logs/ConvNet', graph=sess.graph)
            step = 0

            imgs = []
            labels = []

            ## Maybe is better to put the following two lines in a method outside training()
            ## and call it before training
            
            # convert the generator object returned from dataset.getDataset() in list of tuple
            imgs_labels = list(imgs_labels)
            # split list of tuple in images and labels lists
            img, lab = zip(*imgs_labels)
            
            """
            This is prefereable than this other two options

            img = [x for x,_ in a]
            lab = [x for _,x in a]

            img = list(map(itemgetter(0), a))
            lab = list(map(itemgetter(1), a))
            """

            log.info('Dataset created - images list and labels list')
            log.info('Now split images and labels in Training and Test set...')

            idx = int(4 * img_count/5)

            # Split images and labels
            train_imgs = imgs[0:idx]
            train_labels = labels[0:idx]
            test_imgs    = imgs[idx:img_count]
            test_labels  = labels[idx:img_count]

            # Run for epoch
            for epoch in range(self.max_epochs):
                avg_cost = 0.
                num_batch = int(len(train_imgs)/BATCH_SIZE) # 8
                
                # Loop over all batches
                for step in range(num_batch):

                    batch_imgs, batch_labels = self.nextBatch(train_imgs, train_labels, step, BATCH_SIZE)

                    # Fit training using batch data
                    # print("IMG_PL = ", self.img_pl.get_shape())
                    _, single_cost = sess.run([optimizer, cost], feed_dict={self.img_pl: batch_imgs, self.label_pl: batch_labels, self.keep_prob: dropout})
                    # Compute average loss
                    avg_cost += single_cost

                    # Display logs per epoch step
                    if step % self.display_step == 0:
                        print "Step %03d - Epoch %03d/%03d cost: %.9f - single %.9f" % (step, epoch, self.max_epochs, avg_cost/step, single_cost)
                        log.info("Step %03d - Epoch %03d - cost: %.9f - single %.9f" % (step, epoch, avg_cost/step, single_cost))
                        # Calculate training batch accuracy
                        train_acc, train_loss = sess.run([accuracy, cost], feed_dict={self.img_pl: batch_imgs, self.label_pl: batch_labels, self.keep_prob: 1.})
                        # Calculate training batch loss
                        #train_loss = sess.run(cost, feed_dict={self.img_pl: batch_imgs, self.label_pl: batch_labels, self.keep_prob: 1.})
                        print "Training Accuracy = " + "{:.5f}".format(train_acc)
                        log.info("Training Accuracy = " + "{:.5f}".format(train_acc))
                        print "Training Loss = " + "{:.6f}".format(train_loss)
                        log.info("Training Loss = " + "{:.6f}".format(train_loss))

            print "Optimization Finished!"

            # Save the models to disk
            save_model_ckpt = self.saver.save(sess, "/tmp/model.ckpt")
            print("Model saved in file %s" % save_model_ckpt)

            # Test accuracy
            test_acc = sess.run(accuracy, feed_dict={self.img_pl: test_imgs, self.label_pl: test_labels, self.keep_prob: 1.})
            print "Test accuracy: %.3f" % (test_acc)
            log.info("Test accuracy: %.3f" % (test_acc))

    def prediction(self, img_path):
        with tf.Session() as sess:

            # Construct model
            pred = self.alex_net_model(self.img_pl, self.weights, self.biases, self.keep_prob)

            pred = tf.argmax(pred,1)

            # check if image is a correct JPG file
            if(os.path.isfile(img_path) and (img_path.endswith('jpeg') or
                                             (img_path.endswith('jpg')))):
                # Read image and convert it
                img_bytes = tf.read_file(img_path)
                #img_u8 = tf.image.decode_jpeg(img_bytes, channels=3)
                img_u8 = tf.image.decode_jpeg(img_bytes, channels=1)
                img_u8_eval = sess.run(img_u8)
                image = tf.image.convert_image_dtype(img_u8_eval, tf.float32)
                img_padded_or_cropped = tf.image.resize_image_with_crop_or_pad(image, IMG_SIZE, IMG_SIZE)
                #img_padded_or_cropped = tf.reshape(img_padded_or_cropped, shape=[IMG_SIZE*IMG_SIZE, 3])
                img_padded_or_cropped = tf.reshape(img_padded_or_cropped, shape=[IMG_SIZE * IMG_SIZE])
                # eval
                img_eval = img_padded_or_cropped.eval()

                # Restore model.
                ckpt = tf.train.get_checkpoint_state("/tmp/")
                if(ckpt):
                    self.saver.restore(sess, "/tmp/model.ckpt")
                    print("Model restored")
                else:
                    print "No model checkpoint found to restore - ERROR"
                    return

                # Run the model to get predictions
                predict = sess.run(pred, feed_dict={self.img_pl: [img_eval], self.keep_prob: 1.})
                print predict

            else:
                print "ERROR IMAGE"


### MAIN ###
def main():

    # args from command line:
    # 1) learning_rate
    # 2) max_epochs
    # 3) display_step
    # 4) std_dev
    learning_rate = float(sys.argv[1])
    max_epochs = int(sys.argv[2])
    display_step = int(sys.argv[3])
    std_dev = float(sys.argv[4])

    log.basicConfig(filename='FileLog.log', level=log.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    
    # create the object ConvNet
    conv_net = ConvNet(learning_rate, max_epochs, display_step, std_dev)

    # TRAINING
    conv_net.training()

    # PREDICTION
    # for dirName in os.listdir(IMAGE_DIR):
    #     path = os.path.join(IMAGE_DIR, dirName)
    #     for img in os.listdir(path):
    #         print "reading image to classify... "
    #         img_path = os.path.join(path, img)
    #         conv_net.prediction(img_path)
    #         print("IMG PATH = ", img_path)


if __name__ == '__main__':
    main()
    
