import subprocess
import shlex
from .filesystem import CONFIG
from .error import BuildError
from pathlib import Path

# convert to a "rename dict", which is a dictionary with keys that are the file endings which
# should be saved, and values the corresponding names
# outdir must already exist
def compile_tex(proj_dir, outdir=Path("."), output_map={}):
    proc = subprocess.run(shlex.split(CONFIG['latex_compile_command']) + 
            [f"-outdir={str(outdir)}"] + \
            [CONFIG['default_tex_name'] + '.tex'],
            cwd=str(proj_dir),
            capture_output=True)

    if proc.returncode != 0:
        raise BuildError(proc.stderr.decode('ascii'))

    for filetype, target in output_map.items():
        try:
            (outdir / (CONFIG['default_tex_name'] + filetype)).rename(target)
        except FileNotFoundError:
            pass
