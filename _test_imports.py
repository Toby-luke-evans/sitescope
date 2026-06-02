
import sys; sys.path.insert(0, '/mnt/a/AI/sitescope/packages/zoning-core/src'); sys.path.insert(0, '/mnt/a/AI/sitescope/packages/spatial-engine/src')
import zoning_core
print('zoning_core version:', zoning_core.__version__)
from zoning_core.spatial.index import ZoningIndex
print('ZoningIndex import OK')
from zoning_core.bylaws import toronto
print('toronto bylaws import OK')
print('All imports working!')
