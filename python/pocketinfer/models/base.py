from enum import Enum, auto
import logging
import re
import threading
import time
import time
from typing import Optional
import requests
from subprocess import check_output

MODEL_REGISTRY = {}
MODEL_INSTANCES = []
MODEL_EVT = threading.Event()


class ModelNotFoundError(Exception):
    """Exception raised when a model is not found in the registry."""
    def __init__(self, model: str, models: list[str] = []):
        self.model = model
        self.models = models
        super().__init__()
        self.message = f"Model '{model}' not found. Available models: {', '.join(models) if models else 'None'}"

def register_model(model_cls):
    """Class decorator that records a BaseModel subclass in MODEL_REGISTRY."""
    MODEL_REGISTRY[model_cls.__name__] = model_cls
    return model_cls

class ModelState(Enum):
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class ModelManager:
    """ An optional class for tracking active model instances and managing memory allocation.
    Without this class, you may need to check whether a given model service has been started,
    whether it's running, and you may need to manage memory usage manually.
     
    This class will do so automatically, any model instances will be tracked and memory usage managed.
    It will also provide helpers to ensure all models are ready to go before continuing application execution"""

    def __init__(self, timeout=10.0):
        self.logger = logging.getLogger(self.__class__.__module__)
        self.running = False
        self.timeout = timeout
        self.thread = threading.Thread()
        self.cbs = []

    def subscribe_to_state_change(self, cb):
        if cb not in self.cbs:
            self.cbs.append(cb)
    
    def unsubscribe_to_state_change(self, cb):
        if cb in self.cbs:
            self.cbs.remove(cb)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def run(self):
        while self.running:
            signalled = MODEL_EVT.wait(timeout=self.timeout)
            for model in MODEL_INSTANCES:
                prev_state = model.state
                model.update_service_status()
                if prev_state != model.state:
                    for cb in self.cbs:
                        try:
                            cb(model.__class__.__name__, model.state, prev_state)
                        except Exception as e:
                            self.logger.exception(f"Error in state change callback: {str(e)}")
            if signalled:
                MODEL_EVT.clear()
    
    def check_state(self, model_name: str) -> ModelState:
        """Check the current state of a specific model."""
        for model in MODEL_INSTANCES:
            if model.__class__.__name__ == model_name:
                return model.state
        return ModelState.UNKNOWN
    
    def wait_for(self, model_name: str, timeout: Optional[float] = None) -> bool:
        """Wait for a specific model to reach the RUNNING state."""
        for model in MODEL_INSTANCES:
            if model.__class__.__name__ == model_name:
                if model.state == ModelState.RUNNING:
                    return True
                else:
                    self.logger.warning(f"Waiting for model '{model_name}' to reach RUNNING state, currently it's {model.state}")
        start_time = time.time()
        while True:
            for model in MODEL_INSTANCES:
                if model.__class__.__name__ == model_name:
                    if model.state == ModelState.RUNNING:
                        return True
            if timeout is not None and (time.time() - start_time) > timeout:
                return False
            time.sleep(0.1)



class BaseModel:
    """Common interface expected by BaseApplication.verify_dependencies/update_dependencies."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__module__)
        # State will be optionally managed by a manager class
        self.state = ModelState.UNKNOWN
        # Register this model globally: this will be used for ModelManager
        if self not in MODEL_INSTANCES:
            MODEL_INSTANCES.append(self)
            MODEL_EVT.set()
    
    def __del__(self):
        # Destructor: remove any global references to this model.
        if self in MODEL_INSTANCES:
            MODEL_INSTANCES.remove(self)
            MODEL_EVT.set()

    def load_model(self, model_name: str):
        # Load a given model into memory
        # Should be implemented by all subclasses, but may do nothing if model cannot be changed
        raise NotImplementedError
    
    def unload_model(self):
        # Unload model and free up memory
        # Should be implemented by all subclasses, but may do nothing if model cannot be changed
        raise NotImplementedError

    def model_loaded(self) -> bool:
        # Return True if model is currently loaded into memory, False otherwise
        # Should always return True if model cannot be changed
        raise NotImplementedError
    
    def get_memory_usage_gb(self) -> float:
        # For any non-service backed models, it may be totally appropriate for them to use practically no memory at standby
        # (the cost of a small python class is negligible)
        # but ideally this should be overridden by any classes that subclass this base.
        return 0.0

    def verify(self) -> bool:
        # Verify whether inference service is running or not
        # This should evaluate at the application layer that the API is ready to be used
        raise NotImplementedError

    def update(self, args):
        # Pull or update model if supported
        raise NotImplementedError
    
    def update_service_status(self):
        # Default implementation, suitable for simple python inference:
        if self.state != ModelState.RUNNING:
            # assume non-systemd models are always running
            self.state = ModelState.RUNNING


class BaseSystemdModel(BaseModel):
    """Base class for models that interact with systemd services."""
    SYSTEMD_SERVICE = None
    STARTUP_DELAY = 60.0
    BASE_URL = 'http://localhost'

    def __init__(self):
        super().__init__()
        if self.SYSTEMD_SERVICE is None:
            raise ValueError("SYSTEMD_SERVICE must be defined in subclasses.")
        
    def get_memory_usage_gb(self) -> float:
        metrics = self.get_systemd_metrics()
        memory_str = metrics.get("Memory", "0")
        if memory_str.endswith("K"):
            return float(memory_str[:-1]) / (1024 * 1024)
        elif memory_str.endswith("M"):
            return float(memory_str[:-1]) / 1024
        elif memory_str.endswith("G"):
            return float(memory_str[:-1])
        else:
            return float(memory_str) / (1024 * 1024 * 1024)
        
    def get_systemd_metrics(self):
        if self.SYSTEMD_SERVICE is None:
            raise ValueError("SYSTEMD_SERVICE must be defined in subclasses.")
        try:
            # Note - A better way to do this would be over DBUS
            # But this method requires fewer dependencies
            ret = check_output(["systemctl", "status", self.SYSTEMD_SERVICE], text=True)
            matches = re.findall(r'^\s+(Memory|CPU|Active|Main PID|Tasks|Loaded): (\S+).*$', ret, re.MULTILINE)
            return dict(matches)
        except Exception as e:
            raise RuntimeError(f"Failed to check systemd service {self.SYSTEMD_SERVICE}: {e}")
        
    def service_running(self):
        try:
            metrics = self.get_systemd_metrics()
            return metrics.get("Active") == "active"
        except Exception as e:
            return False

    def service_start(self):
        if self.SYSTEMD_SERVICE is None:
            raise ValueError("SYSTEMD_SERVICE must be defined in subclasses.")
        try:
            check_output(["systemctl", "start", self.SYSTEMD_SERVICE], text=True)
        except Exception as e:
            raise RuntimeError(f"Failed to start systemd service {self.SYSTEMD_SERVICE}: {e}")
        ret = self.service_running()
        if ret:
            self.state = ModelState.STARTING
        MODEL_EVT.set()
        return ret
    
    def service_stop(self):
        if self.SYSTEMD_SERVICE is None:
            raise ValueError("SYSTEMD_SERVICE must be defined in subclasses.")
        try:
            check_output(["systemctl", "stop", self.SYSTEMD_SERVICE], text=True)
        except Exception as e:
            raise RuntimeError(f"Failed to stop systemd service {self.SYSTEMD_SERVICE}: {e}")
        ret = not self.service_running()
        if ret:
            self.state = ModelState.STOPPED
        MODEL_EVT.set()
        return ret

    def service_restart(self):
        if self.SYSTEMD_SERVICE is None:
            raise ValueError("SYSTEMD_SERVICE must be defined in subclasses.")
        try:
            check_output(["systemctl", "restart", self.SYSTEMD_SERVICE], text=True)
        except Exception as e:
            raise RuntimeError(f"Failed to restart systemd service {self.SYSTEMD_SERVICE}: {e}")
        ret = self.service_running()
        if ret:
            self.state = ModelState.STARTING
        MODEL_EVT.set()
        return ret

    def verify(self) -> bool:
        if not self.service_running():
            self.service_restart()
        start = time.time()
        while time.time() - start < self.STARTUP_DELAY:
            try:
                requests.get(self.BASE_URL)
                # Any response, 200 or 404 is acceptable
                return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(0.25)
        return False

    def update(self, args):
        raise NotImplementedError
    
    def update_service_status(self):
        # If not running or starting, check to see if service is online
        if self.state in [ModelState.UNKNOWN, ModelState.STOPPED, ModelState.ERROR]:
            if self.service_running():
                self.logger.debug(f"Model {self.__class__.__name__}: Service {self.SYSTEMD_SERVICE} is detected as running, updating state to STARTING.")
                self.state = ModelState.STARTING
            elif self.state == ModelState.UNKNOWN:
                self.state = ModelState.STOPPED
        if self.state == ModelState.STARTING:
            try:
                if self.verify():
                    self.logger.debug(f"Model {self.__class__.__name__}: Service verification success, updating state to RUNNING")
                    self.state = ModelState.RUNNING
            except Exception as e:
                self.logger.exception(f"Model {self.__class__.__name__}: Service verification failed: {str(e)}")
                self.state = ModelState.ERROR
        if self.state == ModelState.RUNNING:
            if not self.service_running():
                self.logger.warning(f"Model {self.__class__.__name__}: Service {self.SYSTEMD_SERVICE} is no longer running, updating state to ERROR.")
                self.state = ModelState.ERROR