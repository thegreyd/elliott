import urllib
import json
import functools
import semver
from elliottlib import exectools

CINCINNATI_BASE_URL = "https://api.openshift.com/api/upgrades_info/v1/graph"

def sort_semver(versions):
    return sorted(versions, key=functools.cmp_to_key(semver.compare), reverse=True)

def get_latest_stable_ocp(version, arch):
    """
    Queries Cincinnati and returns latest release version for the given X.Y version
    Code referenced from Doozer #release_calc_previous
    """
    
    arch = 'amd64' if arch == 'x86_64' else arch
    channel = f'stable-{version}'
    url = f'{CINCINNATI_BASE_URL}?arch={arch}&channel={channel}'
    
    print(f'Querying cincinnati for latest ocp release version {url}')
    
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    content = exectools.urlopen_assert(req).read()
    graph = json.loads(content)
    versions = [node['version'] for node in graph['nodes']]
    descending_versions = sort_semver(versions)
    return descending_versions[0]
