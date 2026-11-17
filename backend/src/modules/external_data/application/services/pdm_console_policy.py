"""
Operations the admin API console never offers, even in critical mode. They
reconfigure the vault itself or bypass the operation list: installing or
removing add-in hooks would run code on every PDM client, the generic
`api/{uri}` writes reach any endpoint, and destroying files or editing vault
users is beyond what diagnosing the sync needs. Glados reaches all of them
through the PDM service account, so a compromised Glados admin account must
not be able to.
"""

from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec

BLOCKED_OPERATION_IDS = frozenset(
    {
        "post_api_configuration_fileserverroot",
        "delete_api_vaultname_configuration_hooks_dll",
        "put_api_vaultname_configuration_hooks_dll",
        "post_api_vaultname_configuration_hooks_url",
        "delete_api_uri",
        "patch_api_uri",
        "post_api_uri",
        "put_api_uri",
        "delete_api_vaultname_files_fileid_folderid_destroy_destroy",
        "delete_api_vaultname_files_fileid_folderid_folderid_destroy_destroy",
        "delete_api_vaultname_folders_folderid_destroy_destroy",
        "put_api_vaultname_users_userid_extended",
        "delete_api_vaultname_users_userid_picture",
        "put_api_vaultname_users_userid_picture",
    }
)


def console_operations(catalogue: tuple[PdmOperationSpec, ...]) -> tuple[PdmOperationSpec, ...]:
    """The catalogue minus the blocked operations."""
    return tuple(spec for spec in catalogue if spec.id not in BLOCKED_OPERATION_IDS)
