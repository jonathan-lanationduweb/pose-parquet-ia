"""Full precision semantic postprocessing for optional OpenVINO runtimes."""
from __future__ import annotations

from typing import Any

import numpy as np


def add_semantic_postprocessing(model: Any, height: int, width: int) -> Any:
    """Fuse the same bilinear class argmax and normalized floor score."""
    import openvino as ov
    from openvino import opset13 as op

    classes, masks = (r.input_value(0) for r in model.get_results())
    shape = op.shape_of(masks, 'i64')
    class_probs = op.slice(op.softmax(classes, 2), np.array([0], np.int64),
                          np.array([150], np.int64), np.array([1], np.int64),
                          np.array([2], np.int64))
    flat_shape = op.concat([op.gather(shape, np.array([0, 1], np.int64),
                                     np.array(0, np.int64)), np.array([-1], np.int64)], 0)
    flat = op.reshape(op.sigmoid(masks), flat_shape, False)
    score_shape = op.concat([np.array([1, 150], np.int64),
                            op.gather(shape, np.array([2, 3], np.int64),
                                      np.array(0, np.int64))], 0)
    scores = op.reshape(op.matmul(op.transpose(class_probs, np.array([0, 2, 1], np.int64)),
                                 flat, False, False), score_shape, False)

    def resize(value: Any) -> Any:
        return op.interpolate(value, np.array([height, width], np.int64),
                              mode='linear_onnx', shape_calculation_mode='sizes',
                              axes=np.array([2, 3], np.int64))

    top = op.topk(resize(scores), np.array(1, np.int32), 1, 'max', 'none',
                 index_element_type='i32')
    labels = op.squeeze(top.output(1), np.array([1], np.int64))
    floor = op.gather(scores, np.array(3, np.int32), np.array(1, np.int32))
    total = op.maximum(op.reduce_sum(scores, np.array([1], np.int64), False),
                       np.array(1e-8, np.float32))
    probability = op.squeeze(resize(op.unsqueeze(op.divide(floor, total),
                                                 np.array([1], np.int64))),
                             np.array([1], np.int64))
    return ov.Model([labels, probability], model.get_parameters(), 'oneformer-semantic')

