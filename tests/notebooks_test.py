import os

import nbformat
from nbconvert.preprocessors.execute import CellExecutionError
from nbconvert.preprocessors import ExecutePreprocessor

from allennlp.testing.test_case import AllenNlpTestCase


class TestNotebooks(AllenNlpTestCase):
    def test_vocabulary_tutorial(self):
        assert self.execute_notebook("allennlp/notebooks/vocabulary.ipynb")

    @staticmethod
    def execute_notebook(notebook_path: str):
        with open(notebook_path) as notebook:
            contents = nbformat.read(notebook, as_version=4)

        execution_processor = ExecutePreprocessor(timeout=60, kernel_name="python3")
        try:
            # Actually execute the notebook in the current working directory.
            execution_processor.preprocess(contents, {'metadata': {'path': os.getcwd()}})
            return True
        except CellExecutionError:
            # This is a big chunk of JSON, but the stack trace makes it reasonably
            # clear which cell the error occurred in, so fixing it by actually
            # running the notebook will probably be easier.
            print(contents)
            return False
