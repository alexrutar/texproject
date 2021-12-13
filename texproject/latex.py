import subprocess
import shlex
from .filesystem import CONFIG
from .error import BuildError

def compile_tex(proj_dir):
    proc = subprocess.run(shlex.split(CONFIG['latex_compile_command']) + \
            [CONFIG['default_tex_name'] + '.tex'],
            cwd=str(proj_dir),
            capture_output=True)

    if proc.returncode != 0:
        raise BuildError(proc.stderr.decode('ascii'))
