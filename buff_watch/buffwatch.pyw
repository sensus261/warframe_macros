"""BuffWatch entry point. Double-click run.bat, or: python buffwatch.pyw [--image FILE_OR_DIR]"""

import argparse

from bw.app import App


def main():
    ap = argparse.ArgumentParser(description="Magnify selected Warframe buff icons.")
    ap.add_argument("--image", help="use a screenshot (or a folder of them) instead of the "
                                    "screen - handy for testing and teaching icons")
    args = ap.parse_args()
    App(image_path=args.image).run()


if __name__ == "__main__":
    main()
