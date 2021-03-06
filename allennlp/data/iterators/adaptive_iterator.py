from collections import defaultdict
from typing import Callable, Dict, List, Tuple
import random
import logging

from overrides import overrides

from allennlp.data import Dataset, Instance
from allennlp.data.iterators.bucket_iterator import BucketIterator
from allennlp.experiments import Registry

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@Registry.register_data_iterator("adaptive")
class AdaptiveIterator(BucketIterator):
    """
    An ``AdaptiveIterator`` is a ``DataIterator`` that varies the batch size to try to optimize
    GPU memory usage.  Because padding lengths are done dynamically, we can have larger batches
    when padding lengths are smaller, maximizing our usage of the GPU.  This is intended only for
    use with very large models that only barely fit on the GPU - if your model is small enough that
    you can easily fit a reasonable batch size on the GPU for your biggest instances, you probably
    should just use a :class:`BucketIterator`.  This is also still largely experimental, because it
    interacts with the learning rate in odd ways, and we haven't yet implemented good algorithms to
    modify the learning rate based on batch size, etc.

    In order for this to work correctly, you need to do two things:

    1. Provide the ``padding_memory_scaling`` function, which gives a big-O bound on memory
       usage given padding lengths. For instance, if you have two TextFields with
       ``sentence_lengths`` which require padding, this might be simply |sentence1| * |sentence2|.
    2. Tune the `adaptive_memory_usage_constant` parameter for your particular model and GPU.
       While tuning this, set ``biggest_batch_first`` to ``True``, which will bypass the adaptive
       grouping step and use the batching of a ``BucketIterator``, returning the biggest batch
       first.  You want to find the largest batch size for which this largest batch actually fits
       on the GPU without running out of memory.  TODO(mattg): make this happen automatically
       somehow.

    Parameters
    ----------
    adaptive_memory_usage_constant : int, required.
        Only relevant if ``use_adaptive_grouping`` is ``True``.  This is a manually-tuned parameter,
        specific to a particular model architecture and amount of GPU memory (e.g., if you change
        the number of hidden layers in your model, this number will need to change). The recommended
        way to tune this parameter is to (1) use a fixed batch size, with ``biggest_batch_first``
        set to ``True``, and find out the maximum batch size you can handle on your biggest instances
        without running out of memory.  Then (2) turn on ``use_adaptive_grouping``, and set this
        parameter so that you get the right batch size for your biggest instances.  If you set the
        log level to ``DEBUG`` in ``scripts/run_model.py``, you can see the batch sizes that are
        computed.
    padding_memory_scaling: Callable[[Dict[str, Dict[str, int]]], float], required.
        This function is used for computing the adaptive batch sizes.  We assume that memory usage
        is a function that looks like this: :math:`M = b * O(p) * c`, where :math:`M` is the memory
        usage, :math:`b` is the batch size, :math:`c` is some constant that depends on how much GPU
        memory you have and various model hyperparameters, and :math:`O(p)` is a function outlining
        how memory usage asymptotically varies with the padding lengths.  Our approach will be to
        let the user effectively set :math:`\\frac{M}{c}` using the ``adaptive_memory_usage_constant``
        above. This function specifies :math:`O(p)`, so we can solve for the batch size :math:`b`.
        The more specific you get in specifying :math:`O(p)` in this function, the better a job we
        can do in optimizing memory usage.
    maximum_batch_size : int, optional (default=10000)
        If we're using adaptive batch sizes, you can use this to be sure you do not create batches
        larger than this, even if you have enough memory to handle it on your GPU.  You might
        choose to do this to keep smaller batches because you like the noisier gradient estimates
        that come from smaller batches, for instance.
    biggest_batch_first : bool, optional (default=False)
        See :class:`BucketIterator`.  If this is ``True``, we bypass the adaptive grouping step, so
        you can tune the ``adaptive_memory_usage_constant``.
    batch_size : int, optional (default=None)
        Only used when ``biggest_batch_first`` is ``True``, used for tuning
        ``adaptive_memory_usage_constant``.
    sorting_keys : List[Tuple[str, str]]
        See :class:`BucketIterator`.
    padding_noise : List[Tuple[str, str]]
        See :class:`BucketIterator`.
    """
    def __init__(self,
                 adaptive_memory_usage_constant: float,
                 padding_memory_scaling: Callable[[Dict[str, Dict[str, int]]], float],
                 maximum_batch_size: int = 10000,
                 biggest_batch_first: bool = False,
                 batch_size: int = None,
                 sorting_keys: List[Tuple[str, str]] = None,
                 padding_noise: float = 0.2) -> None:
        self._padding_memory_scaling = padding_memory_scaling
        self._maximum_batch_size = maximum_batch_size
        self._adaptive_memory_usage_constant = adaptive_memory_usage_constant
        super(AdaptiveIterator, self).__init__(sorting_keys=sorting_keys,
                                               padding_noise=padding_noise,
                                               biggest_batch_first=biggest_batch_first,
                                               batch_size=batch_size)

    @overrides
    def _create_batches(self, dataset: Dataset, shuffle: bool) -> List[List[Instance]]:
        if self._biggest_batch_first:
            return super(AdaptiveIterator, self)._create_batches(dataset, shuffle)
        if self._sorting_keys:
            dataset = self._sort_dataset_by_padding(dataset,
                                                    self._sorting_keys,
                                                    self._padding_noise)
        # Group the instances into different sized batches, depending on how padded they are.
        grouped_instances = self._adaptive_grouping(dataset)
        if shuffle:
            random.shuffle(grouped_instances)
        return grouped_instances

    def _adaptive_grouping(self, dataset: Dataset):
        batches = []
        current_batch = []
        current_lengths = defaultdict(dict)  # type: Dict[str, Dict[str, int]]
        logger.debug("Creating adaptive groups")
        for instance in dataset.instances:
            current_batch.append(instance)
            instance_lengths = instance.get_padding_lengths()
            for field_name in instance_lengths:
                for key in instance_lengths[field_name]:
                    current_lengths[field_name][key] = max(instance_lengths[field_name][key],
                                                           current_lengths[field_name].get(key, -1))
            big_o_memory_constant = self._padding_memory_scaling(current_lengths)
            if (len(current_batch) * big_o_memory_constant > self._adaptive_memory_usage_constant
                        or len(current_batch) > self._maximum_batch_size):
                current_batch.pop()
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    padding_lengths = Dataset(current_batch).get_padding_lengths()
                    logger.debug("Batch size: %d; padding: %s", len(current_batch), padding_lengths)
                batches.append(current_batch)
                current_batch = [instance]
                current_lengths = instance_lengths
        if logger.getEffectiveLevel() <= logging.DEBUG:
            padding_lengths = Dataset(current_batch).get_padding_lengths()
            logger.debug("Batch size: %d; padding: %s", len(current_batch), padding_lengths)
        batches.append(current_batch)
        return batches
