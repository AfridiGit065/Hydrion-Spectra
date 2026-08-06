import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.application import Application


def main():
    return Application().run()


if __name__ == "__main__":
    sys.exit(main())
