from elliottlib import brew, errata, rhcos, cincinnati
from elliottlib.cli.common import cli
from elliottlib.exceptions import BrewBuildException
from elliottlib.util import get_golang_version_from_root_log, red_print

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
@click.pass_obj
def get_golang_versions_cli(runtime, advisory_id, ocp_pullspec, latest, latest_ocp, packages, arch):
    """
    Prints the Go version used to build a component to stdout.

    Usage:

\b
    $ elliott get-golang-versions -a ID

"""
    count_options = sum(map(bool, [advisory_id, ocp_pullspec, latest, latest_ocp]))
    if count_options > 1:
        raise click.BadParameter("Use only one of --advisory, --rhcos, --rhcos-latest, --rhcos-ocp")

    if arch and not (latest or latest_ocp):
        raise click.BadParameter("--arch can only be used with --rhcos-latest, --rhcos-ocp")

    if advisory_id:
        content_type = errata.get_erratum_content_type(advisory_id)
        if content_type == 'docker':
            get_container_golang_versions(advisory_id)
        else:
            get_rpm_golang_versions(advisory_id)
    
    runtime.initialize()
    major = runtime.group_config.vars.MAJOR
    minor = runtime.group_config.vars.MINOR
    version = f'{major}.{minor}'

    build_id = ''
    arch = 'x86_64' if not arch else arch
    
    if latest or latest_ocp:
        if latest:
            print(f'Looking up latest rhcos build id for {version} {arch}')
            build_id = rhcos.latest_build_id(version, arch)
            print(f'Build id found: {build_id}')
        else:
            print(f'Looking up last ocp release for {version} {arch}')
            release = cincinnati.get_latest_stable_ocp(version, arch)
            if not release:
                return
            print(f'OCP release: {release}')
            ocp_pullspec = f'quay.io/openshift-release-dev/ocp-release:{release}-{arch}'
    
    if ocp_pullspec:
        print(f"Looking up rhcos build id for {ocp_pullspec}")
        build_id, arch = rhcos.get_build_from_payload(ocp_pullspec)
        print(f'Build id found: {build_id}')
    
    if build_id:
        nvrs = rhcos.get_rpm_nvrs(build_id, version, arch)
        if packages:
            packages = [p.strip() for p in packages.split(',')]
            nvrs = [p for p in nvrs if p[0] in packages]
        get_rpm_golang_from_nvrs(nvrs)
