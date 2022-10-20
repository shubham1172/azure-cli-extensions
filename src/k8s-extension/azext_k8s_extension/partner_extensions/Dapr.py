# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

# pylint: disable=unused-argument
# pylint: disable=line-too-long
# pylint: disable=too-many-locals
# pylint: disable=too-many-instance-attributes

import copy
from knack.log import get_logger

from .DefaultExtension import DefaultExtension

from ..vendored_sdks.models import (
    Extension,
    PatchExtension,
)

logger = get_logger(__name__)


class Dapr(DefaultExtension):
    def __init__(self):
        # constants for configuration settings.
        self.CLUSTER_TYPE = 'global.clusterType'

    def Create(self, cmd, client, resource_group_name, cluster_name, name, cluster_type, cluster_rp,
               extension_type, scope, auto_upgrade_minor_version, release_train, version, target_namespace,
               release_namespace, configuration_settings, configuration_protected_settings,
               configuration_settings_file, configuration_protected_settings_file):
        """ExtensionType 'Microsoft.Dapr' specific validations & defaults for Create
           Must create and return a valid 'ExtensionInstance' object.
        """

        if cluster_type.lower() == '' or cluster_type.lower() == 'managedclusters':
            configuration_settings[self.CLUSTER_TYPE] = 'managedclusters'

        create_identity = False
        extension_instance = Extension(
            extension_type=extension_type,
            auto_upgrade_minor_version=auto_upgrade_minor_version,
            release_train=release_train,
            version=version,
            scope=scope,
            configuration_settings=configuration_settings,
            configuration_protected_settings=configuration_protected_settings,
            identity=None,
            location=""
        )
        return extension_instance, name, create_identity

    def Update(self, cmd, resource_group_name: str, cluster_name: str, auto_upgrade_minor_version: bool,
               release_train: str, version: str, configuration_settings: dict,
               configuration_protected_settings: dict, original_extension: Extension, yes: bool = False) \
            -> PatchExtension:

        input_configuration_settings = copy.deepcopy(configuration_settings)

        # configuration_settings can be None, so we need to set it to an empty dict.
        if configuration_settings is None:
            configuration_settings = {}

        # If we are downgrading the extension, then we need to disable the apply-CRDs hook.
        # This is because CRD updates while downgrading can cause issues.
        original_version = original_extension.version
        if original_version and version and version < original_version:
            logger.debug("Downgrade detected from %s to %s. Setting hooks.applyCrds to false.",
                         original_version, version)
            configuration_settings['hooks.applyCrds'] = 'false'
        else:
            # If we are not downgrading, then we need to make sure that the hooks.applyCrds is true.
            # This is because the configuration_settings may have been set to false during a previous
            # downgrade.
            configuration_settings['hooks.applyCrds'] = 'true'

        # If no changes were made, return the original dict (empty or None).
        if len(configuration_settings) == 0:
            configuration_settings = input_configuration_settings

        return PatchExtension(auto_upgrade_minor_version=auto_upgrade_minor_version,
                              release_train=release_train,
                              version=version,
                              configuration_settings=configuration_settings,
                              configuration_protected_settings=configuration_protected_settings)
