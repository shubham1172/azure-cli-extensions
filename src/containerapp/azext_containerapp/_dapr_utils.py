# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from typing import Dict
from azure.cli.core.azclierror import ValidationError
from knack.log import get_logger
from ._clients import ContainerAppClient, DaprComponentPreviewClient
from ._models import (
    DaprComponent as DaprComponentModel,
    DaprServiceComponentBinding as DaprServiceComponentBindingModel,
)

logger = get_logger(__name__)


class DaprUtils:
    supported_dapr_components = {
        "state": ["redis", "postgres"],
        "pubsub": ["kafka", "redis"],
    }

    # TODO: Add test to make sure these items and consts used in custom.py matches, this is to ensure they are in sync.
    @staticmethod
    def _get_supported_services() -> Dict:
        """
        Get the supported services for Dapr along with the create function for each service.
        """
        from .custom import (
            create_redis_service,
            create_postgres_service,
            create_kafka_service,
        )

        return {
            "redis": create_redis_service,
            "postgres": create_postgres_service,
            "kafka": create_kafka_service,
        }

    @staticmethod
    def _get_service_name(service_type: str) -> str:
        """
        Get the service name for the given service type.
        """
        return f"dapr-{service_type}"

    @staticmethod
    def _get_dapr_component_name(component_type: str, service_type: str) -> str:
        """
        Get the Dapr component name for the given component type and service type.

        :param component_type: type of the Dapr component to create, e.g. state or pubsub
        :param service_type: type of the service to create, e.g. redis or kafka
        """
        prefix = "statestore" if component_type == "state" else component_type
        return f"{prefix}-{service_type}"

    @staticmethod
    def get_dapr_component_def_from_service(
        component_type: str,
        service_type: str,
        service_name: str,
        service_id: str,
        component_version: str = "v1",
        component_ignore_errors: bool = False,
    ):
        """
        Get the Dapr component definition for the given component type and service type.

        :param component_type: type of the Dapr component to create, e.g. state or pubsub
        :param service_type: type of the service to create, e.g. redis or kafka
        :param service_name: name of the service to create, e.g. dapr-redis
        :param service_id: id of the service to create, e.g. /subscriptions/.../dapr-redis
        """
        serviceBinding = DaprServiceComponentBindingModel.copy()
        serviceBinding["name"] = service_name
        serviceBinding["serviceId"] = service_id

        component = DaprComponentModel.copy()
        component["properties"]["componentType"] = f"{component_type}.{service_type}"
        component["properties"]["version"] = component_version
        component["properties"]["ignoreErrors"] = component_ignore_errors
        component["properties"]["serviceComponentBind"] = serviceBinding

        return component

    @staticmethod
    def _create_dapr_component_from_service(
        cmd,
        component_type: str,
        service_type: str,
        service_name: str,
        service_id: str,
        resource_group_name: str,
        environment_name: str,
    ):
        """
        Create a Dapr component if it does not exist.
        The component will have bindings to the given service.

        :param component_type: type of the Dapr component to create, e.g. state or pubsub
        :param service_type: type of the service to create, e.g. redis or kafka
        :param service_name: name of the service to create, e.g. dapr-redis
        :param service_id: id of the service to create, e.g. /subscriptions/.../dapr-redis

        :return: Dapr component definition of the component (whether it was created or not)
        """
        if (
            component_type not in DaprUtils.supported_dapr_components.keys()
            or service_type not in DaprUtils.supported_dapr_components[component_type]
        ):
            raise ValidationError(
                f"Component type {component_type} with service type {service_type} is not supported."
            )

        component_name = DaprUtils._get_dapr_component_name(
            component_type, service_type
        )

        # Look up the component, if it already exists, return it.
        logger.debug("Looking up Dapr component %s", component_name)
        component_def = None
        try:
            component_def = DaprComponentPreviewClient.show(
                cmd, resource_group_name, environment_name, component_name
            )
        except Exception:  # pylint: disable=broad-except
            pass

        if component_def is not None:
            logger.warning(
                "Dapr component %s already exists, skipping creation", component_name
            )
            return component_def

        # Create the component.
        logger.debug("Creating Dapr component %s", component_name)
        component_def = DaprUtils.get_dapr_component_def_from_service(
            component_type, service_type, service_name, service_id
        )
        try:
            component = DaprComponentPreviewClient.create_or_update(
                cmd,
                resource_group_name,
                environment_name,
                component_name,
                component_def,
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to create Dapr component {component_name}: {e}"
            ) from e

        if component is None:
            raise ValidationError(
                f"Failed to create Dapr component {component_name}, component definition is None"
            )

        logger.debug("Successfully created Dapr component %s", component_name)
        return component

    @staticmethod
    def _create_service(
        cmd,
        service_type: str,
        service_name: str,
        resource_group_name: str,
        environment_name: str,
    ):
        """
        Create a service if it does not exist.

        :param service_type: type of the service to create, e.g. redis
        :param service_name: name of the service to create, e.g. dapr-redis

        :return: service definition of the service (whether it was created or not)
        """
        supported_services = DaprUtils._get_supported_services()

        if service_type not in supported_services.keys():
            raise ValidationError(f"Service type {service_type} is not supported.")

        # Look up the service, if it already exists, return it.
        logger.debug("Looking up service %s of type %s", service_name, service_type)
        service_def = None
        try:
            service_def = ContainerAppClient.show(
                cmd, resource_group_name, service_name
            )
        except Exception:  # pylint: disable=broad-except
            pass

        if service_def is not None:
            logger.warning(
                "Service %s of type %s already exists, skipping creation",
                service_name,
                service_type,
            )
            return service_def

        # Create the service.
        logger.debug("Creating service %s of type %s", service_name, service_type)
        create_service_func = supported_services[service_type]

        try:
            service_def = create_service_func(
                cmd, service_name, environment_name, resource_group_name
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to create service {service_name} of type {service_type}: {e}"
            ) from e

        if service_def is None:
            raise ValidationError(
                f"Failed to create service {service_name} of type {service_type}, service definition is None"
            )

        logger.debug(
            "Successfully created service %s of type %s", service_name, service_type
        )
        return service_def

    @staticmethod
    def create_service_and_dapr_component(
        cmd,
        component_type: str,
        service_type: str,
        resource_group_name: str,
        environment_name: str,
    ) -> [Dict, Dict]:
        """
        Create a service and a Dapr component with bindings to the service.
        If the service or the Dapr component already exists, skip creation.

        :param component_type: type of the Dapr component to create, e.g. state or pubsub
        :param service_type: type of the service to create, e.g. redis or kafka

        :return definition of the service and the Dapr component (whether they were created newly or not)
        """
        from .custom import safe_get

        service_name = DaprUtils._get_service_name(service_type)
        service_def = DaprUtils._create_service(
            cmd, service_type, service_name, resource_group_name, environment_name
        )
        service_id = safe_get(service_def, "id", default=None)
        if service_id is None:
            raise ValidationError(
                f"Failed to create service {service_name} of type {service_type}, service id is None"
            )

        component_def = DaprUtils._create_dapr_component_from_service(
            cmd,
            component_type,
            service_type,
            service_name,
            service_id,
            resource_group_name,
            environment_name,
        )
        component_id = safe_get(component_def, "id", default=None)
        if component_id is None:
            raise ValidationError(
                f"Failed to create Dapr component of type {component_type} with service type {service_type}"
                ", component id is None"
            )

        return service_id, component_id
