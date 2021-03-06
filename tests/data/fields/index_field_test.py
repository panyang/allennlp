# pylint: disable=no-self-use,invalid-name
import numpy

from allennlp.data.fields import TextField, IndexField
from allennlp.data.token_indexers import SingleIdTokenIndexer
from allennlp.testing.test_case import AllenNlpTestCase


class TestIndexField(AllenNlpTestCase):

    def setUp(self):
        super(TestIndexField, self).setUp()
        self.text = TextField(["here", "is", "a", "sentence", "."],
                              {"words": SingleIdTokenIndexer("words")})

    def test_index_field_inherits_padding_lengths_from_text_field(self):

        index_field = IndexField(4, self.text)
        assert index_field.get_padding_lengths() == {"num_options": 5}

    def test_as_array_converts_field_correctly(self):
        index_field = IndexField(4, self.text)
        array = index_field.as_array(index_field.get_padding_lengths())
        numpy.testing.assert_array_equal(array, numpy.array([0, 0, 0, 0, 1]))

    def test_as_array_handles_none_index_values(self):
        index_field = IndexField(None, self.text)
        array = index_field.as_array(index_field.get_padding_lengths())
        numpy.testing.assert_array_equal(array, numpy.array([0, 0, 0, 0, 0]))
