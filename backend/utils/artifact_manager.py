# backend/utils/artifact_manager.py
import os
from datetime import datetime

def ensure_test_dir(out_dir):
    os.makedirs(out_dir, exist_ok=True)

def _unique_name(base):
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{base}_{ts}"

def save_artifact(test_dir, name, content, binary=False):
    os.makedirs(test_dir, exist_ok=True)
    path = os.path.join(test_dir, name)
    mode = "wb" if binary else "w"
    with open(path, mode) as f:
        if binary:
            f.write(content)
        else:
            f.write(content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else str(content))
    return path
