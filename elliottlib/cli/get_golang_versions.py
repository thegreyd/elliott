from elliottlib import brew, errata, rhcos
from elliottlib.cli.common import cli
from elliottlib.exceptions import BrewBuildException
from elliottlib.util import get_golang_version_from_root_log, red_print

import click


def get_rpm_golang_versions(advisory_id: str):
    all_advisory_nvrs = errata.get_all_advisory_nvrs(advisory_id)

    click.echo("Found {} builds".format(len(all_advisory_nvrs)))
    for nvr in all_advisory_nvrs:
        try:
            root_log = brew.get_nvr_root_log(*nvr)
        except BrewBuildException as e:
            print(e)
            continue
        try:
            golang_version = get_golang_version_from_root_log(root_log)
        except AttributeError:
            print('Could not find Go version in {}-{}-{} root.log'.format(*nvr))
            continue
        print('{}-{}-{}:\t{}'.format(*nvr, golang_version))


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


def _latest_rhcos_source(self, arch, private):
    stream_name = f"{arch}{'-priv' if private else ''}"
    self.runtime.logger.info(f"Getting latest RHCOS source for {stream_name}...")
    try:
        version = self.runtime.get_minor_version()
        build_id, pullspec = rhcos.latest_machine_os_content(version, arch, private)
        if not pullspec:
            raise Exception(f"No RHCOS found for {version}")

        commitmeta = rhcos.rhcos_build_meta(build_id, version, arch, private, meta_type="commitmeta")
        rpm_list = commitmeta.get("rpmostree.rpmdb.pkglist")
        if not rpm_list:
            raise Exception(f"no pkglist in {commitmeta}")

    except Exception as ex:
        problem = f"{stream_name}: {ex}"
        red_print(f"error finding RHCOS {problem}")
        return None

    archive = dict(
        build_id=f"({arch}){build_id}",
        rpms=[dict(name=r[0], epoch=r[1], nvr=f"{r[0]}-{r[2]}-{r[3]}") for r in rpm_list],
    )

    return dict(
        archive=archive,
        image_src=pullspec,
    )


@cli.command("get-golang-versions", short_help="Get version of Go for advisory builds or RHCOS packages")
@click.option('--advisory', '-a', 'advisory_id',
              help="The advisory ID to fetch builds from")
@click.option('--rhcos', '-r', 'ocp_pullspec',
              help='Show version of Go for package builds of RHCOS in the given payload pullspec')
@click.option('--rhcos-latest', '-l', 'latest',
              is_flag=True,
              help='Show version of Go for package builds of RHCOS for latest OCP release. Group must be given')
@click.pass_obj
def get_golang_versions_cli(runtime, advisory_id, ocp_pullspec, latest):
    """
    Prints the Go version used to build a component to stdout.

    Usage:

\b
    $ elliott --group openshift-4.7 get-golang-versions -a ID

\b
    $ elliott --group openshift-4.7 get-golang-versions -r quay.io/openshift-release-dev/ocp-release:4.6.31-x86_64
"""
    count_options = sum(map(bool, [advisory_id, ocp_pullspec, latest]))
    if count_options > 1:
        raise click.BadParameter("Use only one of --advisory, --rhcos, or --rhcos-latest")

    if ocp_pullspec:
        print(ocp_pullspec)
    elif latest:
        runtime.initialize()
    elif advisory_id:
        content_type = errata.get_erratum_content_type(advisory_id)
        if content_type == 'docker':
            get_container_golang_versions(advisory_id)
        else:
            get_rpm_golang_versions(advisory_id)
