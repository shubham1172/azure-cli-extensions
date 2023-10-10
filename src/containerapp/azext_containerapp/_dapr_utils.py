# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from azure.cli.core.azclierror import ValidationError
from knack.log import get_logger
from typing import Dict
from ._clients import ContainerAppClient

logger = get_logger(__name__)


class DaprUtils:
    # TODO: Add test to make sure these items and consts used in custom.py matches, this is to ensure they are in sync.
    def _get_supported_services() -> Dict:
        """
        Get the supported services for Dapr along with the create function for each service.
        """
        from .custom import create_redis_service, create_postgres_service, create_kafka_service
        return {
            "redis": create_redis_service,
            "postgres": create_postgres_service,
            "kafka": create_kafka_service
        }

    @staticmethod
    def _get_service_name(service_type: str) -> str:
        """
        Get the service name for the given service type.
        """
        return f"dapr-{service_type}"

    @staticmethod
    def create_service_if_not_exists(cmd, service_type: str, resource_group_name, environment_name):
        """
        Create a service if it does not exist.
        Returns the service definition of the service (whether it was created or not).

        :param service_type: type of the service to create

        :return: service definition of the service
        """
        supported_services = DaprUtils._get_supported_services()

        if service_type not in supported_services.keys():
            raise ValidationError("Service type {} is not supported.".format(service_type))
        
        service_name = DaprUtils._get_service_name(service_type)
        
        # Look up the service, if it already exists, return it.
        logger.debug("Looking up service %s of type %s", service_name, service_type)
        service_def = None
        try:
            service_def = ContainerAppClient.show(cmd, resource_group_name, service_name)
        except Exception:
            pass

        if service_def is not None:
            logger.warning("Service %s of type %s already exists, skipping creation", service_name, service_type)
            return service_def
        
        # Create the service.
        logger.debug("Creating service %s of type %s", service_name, service_type)
        create_service_func = supported_services[service_type]
        
        try:
            service_def = create_service_func(cmd, service_name, environment_name, resource_group_name)
        except Exception as e:
            raise ValidationError("Failed to create service {} of type {}: {}".format(service_name, service_type, e))
    
        if service_def is None:
            raise ValidationError("Failed to create service {} of type {}, service definition is None".format(service_name, service_type))
        
        logger.debug("Successfully created service %s of type %s", service_name, service_type)
        return service_def