from elliottlib import brew, errata, util
from elliottlib.cli.common import cli
from kobo.rpmlib import parse_nvr
import click


@cli.command("get-golang-versions", short_help="Get version of Go for advisory builds")
@click.option('--advisory', '-a', 'advisory_id',
              help="The advisory ID to fetch builds from")
@click.option('--nvrs', '-n',
              help="Brew nvrs to show go version for. Comma separated")
def get_golang_versions_cli(advisory_id, nvrs):
    """
    Prints the Go version used to build a component to stdout.

    Usage:

\b
    $ elliott get-golang-versions -a 76557

    List brew builds attached to the advisory with their go version

\b
    $ elliott get-golang-versions -n podman-3.0.1-6.el8,podman-1.9.3-3.rhaos4.6.el8

    List given brew builds with their go version
"""
    if advisory_id and nvrs:
        raise click.BadParameter("Use only one of --advisory, --nvrs")

    if advisory_id:
        advisory_nvrs = errata.get_all_advisory_nvrs(advisory_id)
        click.echo(f"Found {len(advisory_nvrs)} builds in advisory {advisory_id}")
        print(advisory_nvrs)

        content_type = errata.get_erratum_content_type(advisory_id)
        if content_type == 'docker':
            util.get_golang_from_nvrs(advisory_nvrs)
        else:
            util.get_golang_from_nvrs(advisory_nvrs, rpm=True)
        return

    if nvrs:
        nvrs = [n.strip() for n in nvrs.split(',')]
        container_nvrs, rpm_nvrs = [], []
        for n in nvrs:
            parsed_nvr = parse_nvr(n)
            nvr_tuple = (parsed_nvr['name'], parsed_nvr['version'], parsed_nvr['release'])
            if 'container' in parsed_nvr['name']:
                container_nvrs.append(nvr_tuple)
            else:
                rpm_nvrs.append(nvr_tuple)
        if rpm_nvrs:
            util.get_golang_from_nvrs(rpm_nvrs, rpm=True)
        if container_nvrs:
            util.get_golang_from_nvrs(container_nvrs)
        return
