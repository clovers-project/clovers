import sys
import traceback

try:
    from PIL import Image
except ImportError as e:
    traceback.print_exc()
    module = None
