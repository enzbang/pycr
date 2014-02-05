"""
Display the code review scores for one or more Gerrit CL.
"""

import argparse

from libpycr.changes import display_change_info, fetch_change_list_or_fail
from libpycr.exceptions import PyCRError
from libpycr.gerrit import Gerrit
from libpycr.utils.commandline import expect_changes_as_positional
from libpycr.utils.output import Formatter, Token
from libpycr.utils.system import warn


def parse_command_line(arguments):
    """
    Parse the SHOW command command-line arguments.

    PARAMETERS
        arguments: a list of command-line arguments to parse

    RETURNS
        a list of ChangeInfo
    """

    parser = argparse.ArgumentParser(
        description='display code reviews for change(s)')
    expect_changes_as_positional(parser)

    cmdline = parser.parse_args(arguments)

    # Fetch changes details
    return fetch_change_list_or_fail(cmdline.changes)


def main(arguments):
    """
    The entry point for the SHOW command.

    List the reviewers of a change.

    PARAMETERS
        arguments: a list of command-line arguments to parse
    """

    changes = parse_command_line(arguments)
    assert changes, 'unexpected empty list'

    for idx, change in enumerate(changes):
        try:
            reviews = Gerrit.get_reviews(change.uuid)

        except PyCRError as why:
            warn('%s: cannot list reviewers' % change.change_id[:9], why)

        if idx:
            print ''

        display_change_info(change)

        for review in reviews:
            print ''
            print '    Reviewer: %s' % review.reviewer

            for label, score in review.approvals:
                if score in ('+1', '+2'):
                    token = Token.Review.OK
                elif score in ('-1', '-2'):
                    token = Token.Review.KO
                else:
                    token = Token.Review.NONE

                print '    %s' % Formatter.format([
                    (None, label),
                    (None, ': '),
                    (token, score)
                ])
