#!/usr/bin/env python3
import sys
import argparse
import logging
import time
from pocketinfer.applications import *
from pocketinfer.applications.registry import ApplicationRegistry
from pocketinfer.board import Board


def main(args):
    # Temporary code to test application startup
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    logging.debug(ApplicationRegistry._classes)
    if args.list_apps:
        print("Available applications:")
        for name in ApplicationRegistry._classes.keys():
            print(f"  {name}")
        return 0
    app_cls = ApplicationRegistry.get_application(args.app)
    if app_cls is None: 
        logging.error("Application not found")
        return 1

    if args.update_app:
        app_cls.update_dependencies()
        return 0

    board = Board.get_board()
    board.statusbar("Start: {}".format(args.app))
    board.button_led(False)

    app_cls.verify_dependencies()
    logging.info(f"Starting application: {args.app}")
    app = app_cls(board)
    app.start()
    while app.running:
        time.sleep(1.0)
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PocketInfer Application Runner")
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    parser.add_argument('--app', type=str, default="HearTheWorldEn", help='Name of the application to run')
    parser.add_argument('--list-apps', action='store_true', help='List available applications and exit')
    parser.add_argument('--update_app', action='store_true', default=False, help='Install dependencies for the specified application and exit')
    args = parser.parse_args()
    sys.exit(main(args))