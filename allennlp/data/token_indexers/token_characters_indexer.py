from typing import Dict, List
import itertools

from allennlp.common.params import Params
from allennlp.common.util import pad_sequence_to_length
from allennlp.data import TokenIndexer, Vocabulary
from allennlp.data.tokenizers import CharacterTokenizer
from allennlp.experiments import Registry

# pylint: disable=no-self-use


@Registry.register_token_indexer("characters")
class TokenCharactersIndexer(TokenIndexer[List[int]]):
    """
    This :class:`TokenIndexer` represents tokens as lists of character indices.

    Parameters
    ----------
    namespace : ``str``, optional (default=``token_characters``)
        We will use this namespace in the :class:`Vocabulary` to map the characters in each token
        to indices.
    character_tokenizer : ``CharacterTokenizer``, optional (default=``CharacterTokenizer()``)
        We use a :class:`CharacterTokenizer` to handle splitting tokens into characters, as it has
        options for byte encoding and other things.  The default here is to instantiate a
        ``CharacterTokenizer`` with its default parameters, which uses unicode characters and
        retains casing.
    """
    def __init__(self,
                 namespace: str = 'token_characters',
                 character_tokenizer: CharacterTokenizer = CharacterTokenizer()) -> None:
        self.namespace = namespace
        self.character_tokenizer = character_tokenizer

    # TODO(joelgrus) uncomment these once fix is merged to overrides library
    # @overrides
    def count_vocab_items(self, token: str, counter: Dict[str, Dict[str, int]]):
        for character in self.character_tokenizer.tokenize(token):
            counter[self.namespace][character] += 1

    # @overrides
    def token_to_indices(self, token: str, vocabulary: Vocabulary) -> List[int]:
        indices = []
        for character in self.character_tokenizer.tokenize(token):
            indices.append(vocabulary.get_token_index(character, self.namespace))
        return indices

    # @overrides
    def get_padding_lengths(self, token: List[int]) -> Dict[str, int]:
        return {'num_token_characters': len(token)}

    # overrides
    def get_input_shape(self, num_tokens: int, padding_lengths: Dict[str, int]):
        return (num_tokens, padding_lengths['num_token_characters'])

    # @overrides
    def get_padding_token(self) -> List[int]:
        return []

    # @overrides
    def pad_token_sequence(self,
                           tokens: List[List[int]],
                           desired_num_tokens: int,
                           padding_lengths: Dict[str, int]) -> List[List[int]]:
        padded_tokens = pad_sequence_to_length(tokens, desired_num_tokens, default_value=lambda: [])
        desired_token_length = padding_lengths['num_token_characters']
        longest_token = max(tokens, key=len)
        if desired_token_length > len(longest_token):
            # Since we want to pad to greater than the longest token, we add a
            # "dummy token" to get the speed of itertools.zip_longest.
            padded_tokens.append([0] * desired_token_length)
        # pad the list of lists to the longest sublist, appending 0's
        padded_tokens = list(zip(*itertools.zip_longest(*padded_tokens, fillvalue=0)))
        if desired_token_length > len(longest_token):
            # now we remove the "dummy token" if we appended one.
            padded_tokens.pop()

        # Now we need to truncate all of them to our desired length, and return the result.
        return [list(token[:desired_token_length]) for token in padded_tokens]

    @classmethod
    def from_params(cls, params: Params) -> 'TokenCharactersIndexer':
        """
        Parameters
        ----------
        namespace : ``str``, optional (default=``token_characters``)
            We will use this namespace in the :class:`Vocabulary` to map the characters in each token
            to indices.
        character_tokenizer : ``Params``, optional (default=``Params({})``)
            We use a :class:`CharacterTokenizer` to handle splitting tokens into characters, as it has
            options for byte encoding and other things.  These parameters get passed to the character
            tokenizer.  The default is to use unicode characters and to retain casing.
        """
        namespace = params.pop('namespace', 'token_characters')
        character_tokenizer_params = params.pop('character_tokenizer', {})
        character_tokenizer = CharacterTokenizer.from_params(character_tokenizer_params)
        params.assert_empty(cls.__name__)
        return cls(namespace=namespace, character_tokenizer=character_tokenizer)
