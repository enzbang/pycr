"""
Display the code review scores for one or more Gerrit CL.
"""

import argparse

from libpycr.changes import fetch_change_list_or_fail
from libpycr.exceptions import PyCRError
from libpycr.gerrit import Gerrit
from libpycr.meta import Builtin
from libpycr.pager import Pager
from libpycr.utils.commandline import expect_changes_as_positional
from libpycr.utils.output import Formatter, NEW_LINE
from libpycr.utils.system import warn


class Show(Builtin):
    """Implement the SHOW command."""

    @property
    def description(self):
        """Inherited."""
        return 'display the change(s) details'

    @staticmethod
    def parse_command_line(arguments):
        """
        Parse the SHOW command command-line arguments.

        PARAMETERS
            arguments: a list of command-line arguments to parse

        RETURNS
            a list of ChangeInfo
        """

        parser = argparse.ArgumentParser(
            description='Display code review scores for change(s).')
        expect_changes_as_positional(parser)

        cmdline = parser.parse_args(arguments)

        # Fetch changes details
        return fetch_change_list_or_fail(cmdline.changes)

    @staticmethod
    def tokenize(idx, change, reviews, patch):
        """
        Token generator for the output.

        PARAMETERS
            idx: index of the change in the list of changes to fetch
            change: the ChangeInfo corresponding to the change
            reviews: the reviews attached to the change
            patch: the patch to display along the change

        RETURNS
            a stream of tokens: tuple of (Token, string)
        """

        if idx:
            yield NEW_LINE

        for token in change.tokenize():
            yield token
        yield NEW_LINE

        for review in reviews:
            yield NEW_LINE

            for token in review.tokenize():
                yield token

            yield NEW_LINE

        yield NEW_LINE

        for token in Formatter.tokenize_diff(patch):
            yield token

    def run(self, arguments, *args, **kwargs):
        """Inherited."""

        changes = Show.parse_command_line(arguments)
        assert changes, 'unexpected empty list'

        with Pager(command=self.name):
            for idx, change in enumerate(changes):
                try:
                    reviews = Gerrit.get_reviews(change.uuid)
                    patch = Gerrit.get_patch(change.uuid)

                except PyCRError as why:
                    warn('%s: cannot list reviewers' % change.change_id[:9],
                         why)
                    continue

                print Formatter.format(
                    Show.tokenize(idx, change, reviews, patch))
