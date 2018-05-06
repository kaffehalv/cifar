from keras.layers import Conv2D, BatchNormalization, Activation
from keras.layers import Dropout
from keras.layers import MaxPooling2D
from keras.layers import GlobalAveragePooling2D
from keras.layers import Dense
from keras.layers import Softmax
from keras import backend as K
from binary_utils import BinaryConv2D, Binarization


class BiNet():
    def __init__(self,
                 conv_type="binary",
                 activation="binary",
                 kernel_epsilon=1e-4,
                 kernel_noise_stddev=1e-2,
                 activity_epsilon=1e-1,
                 activity_noise_stddev=0.0,
                 test_hard=True,
                 input_shape=(32, 32, 3),
                 classes=10):
        self.use_bias = False
        self.scale = False
        self.input_shape = input_shape
        self.classes = classes

        self.pool_size = 2
        self.pool_stride = 2
        self.padding = "same"
        self.conv_type = conv_type
        self.activation = activation

        self.kernel_epsilon = kernel_epsilon
        self.kernel_noise_stddev = kernel_noise_stddev
        self.activity_epsilon = activity_epsilon
        self.activity_noise_stddev = activity_noise_stddev

        self.test_hard = test_hard
        self.weight_reg_factor = 1e-6
        self.dropout_rate = 0.5

        self.filters_1 = 32
        self.repeats_1 = 2

        self.filters_2 = 64
        self.repeats_2 = 2

        self.filters_3 = 128
        self.repeats_3 = 2

        self.module_id = 0

    def _binary_reg(self, weight_matrix):
        return self.weight_reg_factor * K.sum(
            K.square(K.abs(weight_matrix) - 1.0))

    def _activation(self, x, name, is_dense=False):
        activation_name = name + "_" + self.activation
        if (self.activation == "binary"):
            x = Binarization(
                epsilon=self.activity_epsilon,
                activity_regularizer=self._binary_reg,
                test_hard=self.test_hard,
                name=activation_name)(x)
        elif (self.activation == "prelu"):
            if is_dense:
                x = PReLU(name=activation_name)(x)
            else:
                x = PReLU(shared_axes=[1, 2], name=activation_name)(x)
        else:
            x = Activation(self.activation, name=activation_name)(x)
        return x

    def _batch_norm(self, x_input, name):
        return BatchNormalization(scale=self.scale, name=name + "_bn")(x_input)

    def _conv_block(self, x, filters, pool, name):
        layer_name = name + "_conv"
        if self.conv_type == "full":
            x = Conv2D(
                filters,
                kernel_size=3,
                use_bias=self.use_bias,
                padding=self.padding,
                name=layer_name)(x)
        elif self.conv_type == "binary":
            x = BinaryConv2D(
                filters,
                kernel_size=3,
                kernel_regularizer=self._binary_reg,
                kernel_epsilon=self.kernel_epsilon,
                kernel_noise_stddev=self.kernel_noise_stddev,
                test_hard=self.test_hard,
                use_bias=self.use_bias,
                padding=self.padding,
                name=layer_name)(x)
        if pool:
            x = MaxPooling2D(
                pool_size=self.pool_size,
                strides=self.pool_stride,
                name=name + "_maxpool")(x)
        x = self._batch_norm(x, name=name)
        x = self._activation(x, name=name)
        return x

    def _module(self, x, filters, repeats):
        self.module_id += 1
        name = "m" + str(self.module_id)
        for n in range(repeats):
            unit_name = name + "_b" + str(n)
            if n == (repeats - 1):
                x = self._conv_block(
                    x, filters=filters, pool=True, name=unit_name)
            else:
                x = self._conv_block(
                    x, filters=filters, pool=False, name=unit_name)
        return x

    def build(self, x):
        x = self._module(x, filters=self.filters_1, repeats=self.repeats_1)

        x = self._module(x, filters=self.filters_2, repeats=self.repeats_2)

        x = self._module(x, filters=self.filters_3, repeats=self.repeats_3)

        x = GlobalAveragePooling2D(name="global_avg_pool")(x)

        if self.dropout_rate > 0.0:
            x = Dropout(rate=self.dropout_rate, name="dropout")(x)

        x = Dense(self.classes, name="dense")(x)
        x = Softmax(name="softmax")(x)
        return x