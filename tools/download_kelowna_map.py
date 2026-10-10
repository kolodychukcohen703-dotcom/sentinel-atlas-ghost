from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel_kelowna import ensure_map_cache
print(ensure_map_cache(force=True))
