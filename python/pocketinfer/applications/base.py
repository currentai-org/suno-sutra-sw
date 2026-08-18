import threading
import logging
import importlib

from pocketinfer.models.base import ModelManager


class BaseApplication:
    METADATA = {} # Will be overridden by ApplicationRegistry decorator

    def __init__(self, board, settings=None):
        self.logger = logging.getLogger(__name__)
        self.settings = self.METADATA.get("default_settings", {})
        if settings is not None:
            self.settings.update(settings)
        self.board = board
        self.manager = ModelManager()
        self.thread = threading.Thread()
        self.running = False

    def start(self):
        self.manager.start()
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        self.logger.info("Startup")
        while self.running:
            try:
                self.run()
            except KeyboardInterrupt:
                self.logger.info("Exit")
                self.board.clear_screen()
                self.running = False
            except Exception as e:
                self.logger.exception("Error in application run loop: %s", e)

    def run(self):
        raise NotImplementedError()
    
    def stop(self):
        self.running = False
        self.thread.join()

    def verify_dependencies(self):
        # Verify that all service dependencies are available
        models = self.METADATA.get("models", {})
        for model in models:
            logging.debug(f"Verifying model dependency: {model}")
            package = importlib.import_module(f"pocketinfer.models.{model}")
            model_class = getattr(package, model.capitalize())
            verify_func = getattr(model_class, "verify")
            success = verify_func(models[model])
            if not success:
                # Try to manually update
                update_func = getattr(model_class, "update")
                update_func(models[model])
                # Re-verify
                success = verify_func(models[model])
                if not success:
                    raise RuntimeError(f"Model dependency verification failed for {model}")
        return True

    def update_dependencies(self):
        # Verify that all service dependencies are available
        models = self.METADATA.get("models", {})
        for model in models:
            logging.debug(f"Updating model dependency: {model}")
            package = importlib.import_module(f"pocketinfer.models.{model}")
            model_class = getattr(package, model.capitalize())
            update_func = getattr(model_class, "update")
            update_func(models[model])
        return True
