import os
import subprocess

def _minimal_ext_cmd(cmd):
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        out = subprocess.Popen(cmd, stdout = subprocess.PIPE, env=env).communicate()[0]
        return out

def git_revision():
    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        GIT_REVISION = out.strip().decode('utf-8')
    except OSError:
        GIT_REVISION = "Unknown"

    return GIT_REVISION

def git_url():
    try:
        out = _minimal_ext_cmd(['git', 'remote', '-v'])
        url = out.strip().decode('utf-8').split('\n')[0]
        GIT_URL = "Unknown"
        if url.startswith('origin') and url.endswith('(fetch)'):
              GIT_URL = url.split('\t')[1].split('(fetch)')[0]
    except OSError:
        GIT_URL = "Unknown"

    return GIT_URL.strip()

def git_branch():
    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', '--abbrev-ref','HEAD'])
        GIT_BRANCH = out.strip().decode('utf-8')
    except OSError:
        GIT_BRANCH = "Unknown"

    return GIT_BRANCH
