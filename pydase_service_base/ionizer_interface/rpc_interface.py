import inspect
from enum import Enum
from typing import Any

from pydase import DataService
from pydase.components import NumberSlider
from pydase.data_service.data_service_observer import DataServiceObserver
from pydase.units import Quantity
from pydase.utils.helpers import get_object_attr_from_path
from pydase.utils.serialization.serializer import dump
from pydase.utils.serialization.types import SerializedObject
from pydase.version import __version__


class RPCInterface:
    """RPC interface to be passed to tiqi_rpc.Server to interface with Ionizer."""

    def __init__(
        self, data_service_observer: DataServiceObserver, *args: Any, **kwargs: Any
    ) -> None:
        self._data_service_observer = data_service_observer
        self._state_manager = self._data_service_observer.state_manager
        self._service = self._state_manager.service

    async def version(self) -> str:
        return f"pydase v{__version__}"

    async def name(self) -> str:
        return self._service.__class__.__name__

    async def get_props(self) -> SerializedObject:
        return self._service.serialize()["value"]  # type: ignore

    async def get_param(self, full_access_path: str) -> Any:
        """Returns the value of the parameter given by the full_access_path.

        This method is called when Ionizer initilizes the Plugin or refreshes. The
        widgets need to store the full_access_path in their name attribute.
        """
        param = get_object_attr_from_path(self._service, full_access_path)
        if isinstance(param, NumberSlider):
            return param.value
        if isinstance(param, DataService):
            return param.serialize()
        if inspect.ismethod(param):
            # explicitly serialize any methods that will be returned
            full_access_path = param.__name__
            args = inspect.signature(param).parameters
            return f"{full_access_path}({', '.join(args)})"
        if isinstance(param, Enum):
            return param.value
        if isinstance(param, Quantity):
            return param.m
        return param

    async def set_param(self, full_access_path: str, value: Any) -> None:
        parent_path = ".".join(full_access_path.split(".")[:-1])
        parent_object = get_object_attr_from_path(self._service, parent_path)
        attr_name = full_access_path.split(".")[-1]
        # I don't want to trigger the execution of a property getter as this might take
        # a while when connecting to remote devices
        if not isinstance(
            getattr(type(parent_object), attr_name, None),
            property,
        ):
            current_value = getattr(parent_object, attr_name, None)
            if isinstance(current_value, Enum) and isinstance(value, int):
                # Ionizer sets the enums using the position of the definition order
                # This works as definition order is kept, see e.g.
                # https://docs.python.org/3/library/enum.html#enum.EnumType.__iter__
                # I need to use the name attribute as this is what
                # DataService.__set_attribute_based_on_type expects
                value = list(current_value.__class__)[value].name
            if isinstance(current_value, Quantity):
                value = value * current_value.u
            elif isinstance(current_value, NumberSlider):
                full_access_path = full_access_path + "value"

        self._state_manager.set_service_attribute_value_by_path(
            full_access_path, dump(value)
        )

    async def remote_call(self, full_access_path: str, *args: Any) -> Any:
        method_object = get_object_attr_from_path(self._service, full_access_path)
        return method_object(*args)

    async def emit(self, message: str) -> None:
        self.notify(message)

    def notify(self, message: str) -> None:
        """
        This method will be overwritten by the tiqi-rpc server.

        Args:
            message (str): Notification message.
        """
        return
