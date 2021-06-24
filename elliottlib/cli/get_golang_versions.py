from elliottlib import brew, errata, rhcos, cincinnati, util
from elliottlib.cli.common import cli
from elliottlib.exceptions import BrewBuildException

import click
import functools
import semver
import urllib
import json


def get_rpm_golang_versions(advisory_id: str):
    advisory_nvrs = errata.get_all_advisory_nvrs(advisory_id)
    click.echo(f"Found {len(advisory_nvrs)} builds in advisory {advisory_id}")
    print(advisory_nvrs)
    brew.get_rpm_golang_from_nvrs(advisory_nvrs)


def get_container_golang_versions(advisory_id: str):
    all_builds = errata.get_brew_builds(advisory_id)

    all_build_objs = brew.get_build_objects([b.nvr for b in all_builds])
    for build in all_build_objs:
        golang_version = None
        name = build.get('name')
        try:
            parents = build['extra']['image']['parent_image_builds']
        except KeyError:
            print('Could not get parent image info for {}'.format(name))
            continue

        for p, pinfo in parents.items():
            if 'builder' in p:
                golang_version = pinfo.get('nvr')

        if golang_version is not None:
            print('{}:\t{}'.format(name, golang_version))


@cli.command("get-golang-versions", short_help="Get version of Go for advisory builds")
@click.option('--advisory', '-a', 'advisory_id',
              help="The advisory ID to fetch builds from")
@click.option('--nvrs', '-n',
              help="Brew nvrs to show go version for. Comma separated")
@click.pass_obj
def get_golang_versions_cli(runtime, advisory_id, nvrs):
    """
    Prints the Go version used to build a component to stdout.

    Usage:

\b
    $ elliott get-golang-versions -a ID

\b
    $ elliott get-golang-versions -n podman-1.9.3-3.rhaos4.6.el8

"""
    if advisory_id and nvrs:
        raise click.BadParameter("Use only one of --advisory, --nvrs")

    if advisory_id:
        content_type = errata.get_erratum_content_type(advisory_id)
        if content_type == 'docker':
            get_container_golang_versions(advisory_id)
        else:
            get_rpm_golang_versions(advisory_id)
        return

    if nvrs:
        nvrs = [n.strip().split('-') for n in nvrs.split(',')]
        for n in nvrs:
            if len(n) < 3:
                print(f'Invalid nvr: {n}')
                return
    util.get_rpm_golang_from_nvrs(nvrs)
