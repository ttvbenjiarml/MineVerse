import os
import sys
import subprocess
import glob

here = os.path.dirname(os.path.dirname(__file__))

dists = glob.glob(os.path.join(here, 'dist', '*'))
if not dists:
    print('No distributions found in', os.path.join(here, 'dist'))
    sys.exit(1)

token = os.environ.get('PYPI_API_TOKEN') or os.environ.get('TWINE_PASSWORD')

cmd = [sys.executable, '-m', 'twine', 'upload'] + dists
if token:
    print('Using PYPI_API_TOKEN from environment.')
    cmd += ['-u', '__token__', '-p', token]
else:
    print('No PYPI_API_TOKEN found; attempting upload with configured credentials (.pypirc or interactive twine).')

print('Running:', ' '.join(cmd))
try:
    subprocess.check_call(cmd)
except subprocess.CalledProcessError as e:
    print('Upload failed:', e)
    sys.exit(e.returncode)
print('Upload completed successfully.')
