# Copyright (c) 2014 The Johns Hopkins University/Applied Physics Laboratory
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from kmip.core.factories.payloads import PayloadFactory

from kmip.core.messages.payloads import activate
from kmip.core.messages.payloads import create
from kmip.core.messages.payloads import create_key_pair
from kmip.core.messages.payloads import decrypt
from kmip.core.messages.payloads import destroy
from kmip.core.messages.payloads import derive_key
from kmip.core.messages.payloads import discover_versions
from kmip.core.messages.payloads import encrypt
from kmip.core.messages.payloads import get
from kmip.core.messages.payloads import get_attribute_list
from kmip.core.messages.payloads import get_attributes
from kmip.core.messages.payloads import locate
from kmip.core.messages.payloads import query
from kmip.core.messages.payloads import rekey_key_pair
from kmip.core.messages.payloads import register
from kmip.core.messages.payloads import revoke
from kmip.core.messages.payloads import mac


class ResponsePayloadFactory(PayloadFactory):

    def _create_create_payload(self):
        return create.CreateResponsePayload()

    def _create_create_key_pair_payload(self):
        return create_key_pair.CreateKeyPairResponsePayload()

    def _create_register_payload(self):
        return register.RegisterResponsePayload()

    def _create_derive_key_payload(self):
        return derive_key.DeriveKeyResponsePayload()

    def _create_rekey_key_pair_payload(self):
        return rekey_key_pair.RekeyKeyPairResponsePayload()

    def _create_locate_payload(self):
        return locate.LocateResponsePayload()

    def _create_get_payload(self):
        return get.GetResponsePayload()

    def _create_get_attribute_list_payload(self):
        return get_attribute_list.GetAttributeListResponsePayload()

    def _create_get_attributes_payload(self):
        return get_attributes.GetAttributesResponsePayload()

    def _create_destroy_payload(self):
        return destroy.DestroyResponsePayload()

    def _create_query_payload(self):
        return query.QueryResponsePayload()

    def _create_discover_versions_payload(self):
        return discover_versions.DiscoverVersionsResponsePayload()

    def _create_activate_payload(self):
        return activate.ActivateResponsePayload()

    def _create_revoke_payload(self):
        return revoke.RevokeResponsePayload()

    def _create_mac_payload(self):
        return mac.MACResponsePayload()

    def _create_encrypt_payload(self):
        return encrypt.EncryptResponsePayload()

    def _create_decrypt_payload(self):
        return decrypt.DecryptResponsePayload()
