import tensorflow as tf


def build_model(
    input_shape: tuple[int, int, int] = (224, 224, 3),
    num_classes: int = 8,
) -> tf.keras.Model:
    """Build a small CNN image classifier model.

    Parameters
    - input_shape: Image input shape as (H, W, C).
    - num_classes: Number of output classes.

    Returns:
    - A compiled Keras ``Model`` ready for training.
    """
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Conv2D(32, (3, 3), activation="relu", input_shape=input_shape),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(64, (3, 3), activation="relu"),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(128, (3, 3), activation="relu"),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dense(num_classes, activation="softmax"),
        ]
    )

    return model
