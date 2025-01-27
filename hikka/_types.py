import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from .inline.types import *  # noqa: F401, F403
from . import validators  # noqa: F401

from telethon.tl.types import Message

logger = logging.getLogger(__name__)


class Module:
    strings = {"name": "Unknown"}

    """There is no help for this module"""

    def config_complete(self):
        """Called when module.config is populated"""

    async def client_ready(self, client, db):
        """Called after client is ready (after config_loaded)"""

    async def on_unload(self):
        """Called after unloading / reloading module"""

    async def on_dlmod(self, client, db):
        """
        Called after the module is first time loaded with .dlmod or .loadmod

        Possible use-cases:
        - Send reaction to author's channel message
        - Join author's channel
        - Create asset folder
        - ...

        ⚠️ Note, that any error there will not interrupt module load, and will just
        send a message to logs with verbosity INFO and exception traceback
        """


class LoadError(Exception):
    """Tells user, why your module can't be loaded, if rased in `client_ready`"""

    def __init__(self, error_message: str):  # skipcq: PYL-W0231
        self._error = error_message

    def __str__(self) -> str:
        return self._error


class SelfUnload(Exception):
    """Silently unloads module, if raised in `client_ready`"""

    def __init__(self, error_message: Optional[str] = ""):  # skipcq: PYL-W0231
        self._error = error_message

    def __str__(self) -> str:
        return self._error


class StopLoop(Exception):
    """Stops the loop, in which is raised"""


class ModuleConfig(dict):
    """Stores config for each mod, that needs them"""

    def __init__(self, *entries):
        if all(isinstance(entry, ConfigValue) for entry in entries):
            # New config format processing
            self._config = {config.option: config for config in entries}
        else:
            # Legacy config processing
            keys = []
            values = []
            defaults = []
            docstrings = []
            for i, entry in enumerate(entries):
                if i % 3 == 0:
                    keys += [entry]
                elif i % 3 == 1:
                    values += [entry]
                    defaults += [entry]
                else:
                    docstrings += [entry]

            self._config = {
                key: ConfigValue(option=key, default=default, doc=doc)
                for key, default, doc in zip(keys, defaults, docstrings)
            }

        super().__init__(
            {option: config.value for option, config in self._config.items()}
        )

    def getdoc(self, key: str, message: Message = None) -> str:
        """Get the documentation by key"""
        ret = self._config[key].doc

        if callable(ret):
            try:
                # Compatibility tweak
                # does nothing in Hikka
                ret = ret(message)
            except Exception:
                ret = ret()

        return ret

    def getdef(self, key: str) -> str:
        """Get the default value by key"""
        return self._config[key].default

    def __setitem__(self, key: str, value: Any) -> bool:
        self._config[key].value = value
        return dict.__setitem__(self, key, value)

    def __getitem__(self, key: str) -> Any:
        try:
            return self._config[key].value
        except KeyError:
            return None


class _Placeholder:
    """Placeholder to determine if the default value is going to be set"""


@dataclass(repr=True)
class ConfigValue:
    option: str
    default: Any = None
    doc: Union[callable, str] = "No description"
    value: Any = field(default_factory=_Placeholder)
    validator: Optional[callable] = None

    def __post_init__(self):
        if isinstance(self.value, _Placeholder):
            self.value = self.default

    def __setattr__(self, key: str, value: Any) -> bool:
        if key == "value":
            if self.validator is not None and value is not None:
                value = self.validator.validate(value)

            # This attribute will tell the `Loader` to save this value in db
            self._save_marker = True

            try:
                value = ast.literal_eval(value)
            except Exception:
                pass

            # Convert value to list if it's tuple just not to mess up
            # with json convertations
            if isinstance(value, (set, tuple)):
                value = list(value)

        object.__setattr__(self, key, value)
