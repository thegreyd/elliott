from __future__ import absolute_import, print_function, unicode_literals
import click
import datetime
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool as ThreadPool
import re
from elliottlib import brew
from elliottlib.exceptions import BrewBuildException

from errata_tool import Erratum
from kerberos import GSSError

# -----------------------------------------------------------------------------
# Constants and defaults
# -----------------------------------------------------------------------------
default_release_date = datetime.datetime(1970, 1, 1, 0, 0)
now = datetime.datetime.now()
YMD = '%Y-%b-%d'


def red_prefix(msg, file=None):
    """Print out a message prefix in bold red letters, like for "Error: "
messages"""
    click.secho(msg, nl=False, bold=True, fg='red', file=file)


def green_prefix(msg, file=None):
    """Print out a message prefix in bold green letters, like for "Success: "
messages"""
    click.secho(msg, nl=False, bold=True, fg='green', file=file)


def yellow_prefix(msg, file=None):
    """Print out a message prefix in bold yellow letters, like for "Warning: "
or Notice: messages"""
    click.secho(msg, nl=False, bold=True, fg='yellow', file=file)


def red_print(msg, file=None):
    """Print out a message in red text"
messages"""
    click.secho(msg, nl=True, bold=False, fg='red', file=file)


def green_print(msg, file=None):
    """Print out a message in green text"""
    click.secho(msg, nl=True, bold=False, fg='green', file=file)


def yellow_print(msg, file=None):
    """Print out a message in yellow text"""
    click.secho(msg, nl=True, bold=False, fg='yellow', file=file)


def cprint(msg):
    """Wrapper for click.echo"""
    click.echo(msg)


def exit_unauthenticated():
    """Standard response when an API call returns 'unauthenticated' (401)"""
    red_prefix("Error Unauthenticated: ")
    click.echo("401 - user is not authenticated, are you sure you have a kerberos ticket?")
    exit(1)


def exit_unauthorized():
    """Standard response when an API call returns 'unauthorized' (403)"""
    red_prefix("Error Unauthorized: ")
    click.echo("403 - user is authenticated, but unauthorized to perform this action")
    exit(1)


def ensure_erratatool_auth():
    """Test (cheaply) that we at least have authentication to erratatool"""
    try:
        Erratum(errata_id=1)
    except GSSError:
        exit_unauthenticated()


def validate_release_date(ctx, param, value):
    """Ensures dates are provided in the correct format"""
    try:
        release_date = datetime.datetime.strptime(value, YMD)
        if release_date == default_release_date:
            # Default date, nothing special to note
            pass
        else:
            # User provided date passed validation, they deserve a
            # hearty thumbs-up!
            green_prefix("User provided release date: ")
            click.echo("{} - Validated".format(release_date.strftime(YMD)))
        return value
    except ValueError:
        raise click.BadParameter('Release date (--date) must be in YYYY-Mon-DD format')


def validate_email_address(ctx, param, value):
    """Ensure that email addresses provided are valid email strings"""
    # Really just check to match /^[^@]+@[^@]+\.[^@]+$/
    email_re = re.compile(r'^[^@ ]+@[^@ ]+\.[^@ ]+$')
    if not email_re.match(value):
        raise click.BadParameter(
            "Invalid email address for {}: {}".format(param, value))

    return value


def release_from_branch(ver):
    """Parse the release version from the provided 'branch'.

For example, if --group=openshift-3.9 then runtime.group_config.branch
will have the value rhaos-3.9-rhel-7. When passed to this function the
return value would be the number 3.9, where in considering '3.9' then
'3.9' is the RELEASE version.

This behavior is HIGHLY dependent on the format of the input
argument. Hence, why this function indicates the results are based on
the 'branch' variable. Arbitrary input will fail. Use of this implies
you read the docs.
    """
    return ver.split('-')[1]


def major_from_branch(ver):
    """Parse the major version from the provided version (or 'branch').

For example, if --group=openshift-3.9 then runtime.group_config.branch
will have the value rhaos-3.9-rhel-7. When passed to this function the
return value would be the number 3, where in considering '3.9' then
'3' is the MAJOR version.

I.e., this gives you the X component if 3.9 => X.Y.

This behavior is HIGHLY dependent on the format of the input
argument. Hence, why this function indicates the results are based on
the 'branch' variable. Arbitrary input will fail. Use of this implies
you read the docs.
    """
    return ver.split('-')[1].split('.')[0]


def minor_from_branch(ver):
    """Parse the minor version from the provided version (or 'branch').

For example, if --group=openshift-3.9 then runtime.group_config.branch
will have the value rhaos-3.9-rhel-7. When passed to this function the
return value would be the number 9, where in considering '3.9' then
'9' is the MINOR version.

I.e., this gives you the Y component if 3.9 => X.Y.

This behavior is HIGHLY dependent on the format of the input
argument. Hence, why this function indicates the results are based on
the 'branch' variable. Arbitrary input will fail. Use of this implies
you read the docs.
    """
    return ver.split('-')[1].split('.')[1]


def pbar_header(msg_prefix='', msg='', seq=[], char='*'):
    """Generate a progress bar header for a given iterable or
sequence. The given sequence must have a countable length. A bar of
`char` characters is printed between square brackets.

    :param string msg_prefix: Header text to print in heavy green text
    :param string msg: Header text to print in the default char face
    :param sequence seq: A sequence (iterable) to size the progress
    bar against
    :param str char: The character to use when drawing the progress
    bar

For example:

    pbar_header("Foo: ", "bar", seq=[None, None, None], char='-')

would produce:

    Foo: bar
    [---]

where 'Foo: ' is printed using green_prefix() and 'bar' is in the
default console fg color and weight.

TODO: This would make a nice context wrapper.

    """
    green_prefix(msg_prefix)
    click.echo(msg)
    click.echo("[" + (char * len(seq)) + "]")


def progress_func(func, char='*', file=None):
    """Use to wrap functions called in parallel. Prints a character for
each function call.

    :param lambda-function func: A 'lambda wrapped' function to call
    after printing a progress character
    :param str char: The character (or multi-char string, if you
    really wanted to) to print before calling `func`
    :param file: the file to print the progress. None means stdout.

    Usage examples:
      * See find-builds command
    """
    click.secho(char, fg='green', nl=False, file=file)
    return func()


def parallel_results_with_progress(inputs, func, file=None):
    """Run a function against a list of inputs with a progress bar

    :param sequence inputs : A sequence of items to iterate over in parallel
    :param lambda-function func: A lambda function to call with one arg to process

    Usage examples:
      * See find-builds command

        candidate_build_infos = parallel_results_with_progress(
            candidate_builds,
            lambda build: build.get_latest_build_info()
        )

    Example output:
    [****************]

    """
    click.secho('[', nl=False, file=file)
    pool = ThreadPool(cpu_count())
    results = pool.map(
        lambda it: progress_func(lambda: func(it), file=file),
        inputs)

    # Wait for results
    pool.close()
    pool.join()
    click.echo(']', file=file)

    return results


def get_target_release(bugs):
    """
    Pass in a list of bugs attached to an advisory and get the target release version back
    """
    invalid_bugs = []
    target_releases = set()
    for bug in bugs:
        # make sure it's a list with a valid str value
        valid_target_rel = isinstance(bug.target_release, list) and len(bug.target_release) > 0 and \
            re.match(r'(\d+.\d+.[0|z])', bug.target_release[0])
        if not valid_target_rel:
            invalid_bugs.append(bug)
        else:
            target_releases.add(bug.target_release[0])

    if invalid_bugs:
        err = 'bug.target_release should be a list with a string matching regex (digit+.digit+.[0|z])'
        for b in invalid_bugs:
            err += f'\n bug.id: {b.id}, bug.target_release: {b.target_release} '
        return '', err

    if len(target_releases) != 1:
        err = f'Found different target_release values for tracker bugs: {target_releases}. ' \
              'There should be only 1 target release for all bugs. Fix the offending bug(s) and try again.'
        return '', err

    return target_releases.pop(), ''


def get_release_version(pv):
    """ there are two kind of format of product_version: OSE-4.1-RHEL-8 RHEL-7-OSE-4.1 RHEL-7-OSE-4.1-FOR-POWER-LE """
    return re.search(r'OSE-(\d+\.\d+)', pv).groups()[0]


def convert_remote_git_to_https(source):
    """
    Accepts a source git URL in ssh or https format and return it in a normalized
    https format:
        - https protocol
        - no trailing /
    :param source: Git remote
    :return: Normalized https git URL
    """
    url = re.sub(
        pattern=r'[^@]+@([^:/]+)[:/]([^\.]+)',
        repl='https://\\1/\\2',
        string=source.strip(),
    )
    return re.sub(string=url, pattern=r'\.git$', repl='').rstrip('/')


def minor_version_tuple(bz_target):
    """
    Turns '4.5' or '4.5.z' into numeric (4, 5)
    Assume the target version begins with numbers 'x.y' - explode otherwise

    :param bz_target: A string like "4.5.0"
    :return: A tuple like (4, 5)
    """
    if bz_target == '---':
        return (0, 0)
    major, minor, _ = f"{bz_target}.z".split('.', 2)
    return (int(major), int(minor))


def get_golang_version_from_build_log(log):
    # TODO add a test for this
    # Based on below greps:
    # $ grep -m1 -o -E '(go-toolset-1[^ ]*|golang-(bin-|))[0-9]+.[0-9]+.[0-9]+[^ ]*' ./3.11/*.log | sed 's/:.*\([0-9]\+\.[0-9]\+\.[0-9]\+.*\)/: \1/'
    # $ grep -m1 -o -E '(go-toolset-1[^ ]*|golang.*module[^ ]*).*[0-9]+.[0-9]+.[0-9]+[^ ]*' ./4.5/*.log | sed 's/\:.*\([^a-z][0-9]\+\.[0-9]\+\.[0-9]\+[^ ]*\)/:\ \1/'
    m = re.search(r'(go-toolset-1[^\s]*|golang-bin).*[0-9]+.[0-9]+.[0-9]+[^\s]*', log)
    s = " ".join(m.group(0).split())
    return s


def get_golang_container_nvrs(nvrs):
    go_fail, brew_fail = 0, 0
    all_build_objs = brew.get_build_objects([
        '{}-{}-{}'.format(*n) for n in nvrs
    ])
    for build in all_build_objs:
        golang_version = None
        name = build.get('name')
        try:
            parents = build['extra']['image']['parent_image_builds']
        except KeyError:
            brew_fail += 1
            continue

        for p, pinfo in parents.items():
            if 'builder' in p:
                golang_version = pinfo.get('nvr')

        if golang_version:
            print(f'{name} {golang_version}')
        elif 'golang-builder' in name:
            try:
                for n in nvrs:
                    if name in n:
                        build_log = brew.get_nvr_arch_log(*n)
            except BrewBuildException:
                brew_fail += 1
                continue
            try:
                golang_version = get_golang_version_from_build_log(build_log)
            except AttributeError:
                go_fail += 1
                continue
            print(f'{name} {golang_version}')
        else:
            go_fail += 1
    return brew_fail, go_fail


def get_golang_rpm_nvrs(nvrs):
    go_fail, brew_fail = 0, 0
    for nvr in nvrs:
        try:
            root_log = brew.get_nvr_root_log(*nvr)
        except BrewBuildException:
            brew_fail += 1
            continue
        try:
            golang_version = get_golang_version_from_build_log(root_log)
        except AttributeError:
            go_fail += 1
            continue
        nvr_s = '{}-{}-{}'.format(*nvr)
        print(f'{nvr_s} {golang_version}')
    return brew_fail, go_fail


# some of our systems refer to golang's architecture nomenclature; translate between that and brew arches
brew_arches = ["x86_64", "s390x", "ppc64le", "aarch64"]
brew_arch_suffixes = ["", "-s390x", "-ppc64le", "-aarch64"]
go_arches = ["amd64", "s390x", "ppc64le", "arm64"]
go_arch_suffixes = ["", "-s390x", "-ppc64le", "-arm64"]


def go_arch_for_brew_arch(brew_arch: str) -> str:
    if brew_arch in go_arches:
        return brew_arch   # allow to already be a go arch, just keep same
    if brew_arch in brew_arches:
        return go_arches[brew_arches.index(brew_arch)]
    raise Exception(f"no such brew arch '{brew_arch}' - cannot translate to golang arch")


def brew_arch_for_go_arch(go_arch: str) -> str:
    if go_arch in brew_arches:
        return go_arch  # allow to already be a brew arch, just keep same
    if go_arch in go_arches:
        return brew_arches[go_arches.index(go_arch)]
    raise Exception(f"no such golang arch '{go_arch}' - cannot translate to brew arch")


# imagestreams and such often began without consideration for multi-arch and then
# added a suffix everywhere to accommodate arches (but kept the legacy location for x86).
def go_suffix_for_arch(arch: str) -> str:
    arch = go_arch_for_brew_arch(arch)  # translate either incoming arch style
    return go_arch_suffixes[go_arches.index(arch)]


def brew_suffix_for_arch(arch: str) -> str:
    arch = brew_arch_for_go_arch(arch)  # translate either incoming arch style
    return brew_arch_suffixes[brew_arches.index(arch)]
