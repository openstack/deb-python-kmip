# Copyright (c) 2016 The Johns Hopkins University/Applied Physics Laboratory
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

import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes, hmac, cmac
from cryptography.hazmat.primitives import padding as symmetric_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding as \
    asymmetric_padding
from cryptography.hazmat.primitives import ciphers, keywrap
from cryptography.hazmat.primitives.ciphers import algorithms, modes
from cryptography.hazmat.primitives.kdf import hkdf
from cryptography.hazmat.primitives.kdf import kbkdf
from cryptography.hazmat.primitives.kdf import pbkdf2

from kmip.core import enums
from kmip.core import exceptions
from kmip.services.server.crypto import api


class CryptographyEngine(api.CryptographicEngine):
    """
    A cryptographic engine that uses pyca/cryptography to generate
    cryptographic objects and conduct cryptographic operations.
    """

    def __init__(self):
        """
        Construct a CryptographyEngine.
        """
        self.logger = logging.getLogger('kmip.server.engine.cryptography')

        # The IDEA algorithm is supported by cryptography but may not be
        # supported by certain backends, like OpenSSL.
        self._symmetric_key_algorithms = {
            enums.CryptographicAlgorithm.TRIPLE_DES: algorithms.TripleDES,
            enums.CryptographicAlgorithm.AES:        algorithms.AES,
            enums.CryptographicAlgorithm.BLOWFISH:   algorithms.Blowfish,
            enums.CryptographicAlgorithm.CAMELLIA:   algorithms.Camellia,
            enums.CryptographicAlgorithm.CAST5:      algorithms.CAST5,
            enums.CryptographicAlgorithm.IDEA:       algorithms.IDEA,
            enums.CryptographicAlgorithm.RC4:        algorithms.ARC4
        }
        self._asymmetric_key_algorithms = {
            enums.CryptographicAlgorithm.RSA: self._create_rsa_key_pair
        }
        self._hash_algorithms = {
            enums.CryptographicAlgorithm.HMAC_SHA1: hashes.SHA1,
            enums.CryptographicAlgorithm.HMAC_SHA224: hashes.SHA224,
            enums.CryptographicAlgorithm.HMAC_SHA256: hashes.SHA256,
            enums.CryptographicAlgorithm.HMAC_SHA384: hashes.SHA384,
            enums.CryptographicAlgorithm.HMAC_SHA512: hashes.SHA512,
            enums.CryptographicAlgorithm.HMAC_MD5: hashes.MD5
        }

        # TODO(peter-hamilton): Consider merging above hash dict and this one
        self._encryption_hash_algorithms = {
            enums.HashingAlgorithm.MD5:     hashes.MD5,
            enums.HashingAlgorithm.SHA_1:   hashes.SHA1,
            enums.HashingAlgorithm.SHA_224: hashes.SHA224,
            enums.HashingAlgorithm.SHA_256: hashes.SHA256,
            enums.HashingAlgorithm.SHA_384: hashes.SHA384,
            enums.HashingAlgorithm.SHA_512: hashes.SHA512
        }

        # GCM is supported by cryptography but requires inputs that are not
        # supported by the KMIP spec. It is excluded for now.
        self._modes = {
            enums.BlockCipherMode.CBC: modes.CBC,
            enums.BlockCipherMode.ECB: modes.ECB,
            enums.BlockCipherMode.OFB: modes.OFB,
            enums.BlockCipherMode.CFB: modes.CFB,
            enums.BlockCipherMode.CTR: modes.CTR
        }
        self._asymmetric_padding_methods = {
             enums.PaddingMethod.OAEP:     asymmetric_padding.OAEP,
             enums.PaddingMethod.PKCS1v15: asymmetric_padding.PKCS1v15
        }
        self._symmetric_padding_methods = {
            enums.PaddingMethod.ANSI_X923: symmetric_padding.ANSIX923,
            enums.PaddingMethod.PKCS5:     symmetric_padding.PKCS7
        }
        self._no_mode_needed = [
            enums.CryptographicAlgorithm.RC4
        ]
        self._no_padding_needed = [
            enums.BlockCipherMode.CTR,
            enums.BlockCipherMode.OFB,
            enums.BlockCipherMode.CFB,
            enums.BlockCipherMode.GCM
        ]

    def create_symmetric_key(self, algorithm, length):
        """
        Create a symmetric key.

        Args:
            algorithm(CryptographicAlgorithm): An enumeration specifying the
                algorithm for which the created key will be compliant.
            length(int): The length of the key to be created. This value must
                be compliant with the constraints of the provided algorithm.

        Returns:
            dict: A dictionary containing the key data, with the following
                key/value fields:
                * value - the bytes of the key
                * format - a KeyFormatType enumeration for the bytes format

        Raises:
            InvalidField: Raised when the algorithm is unsupported or the
                length is incompatible with the algorithm.
            CryptographicFailure: Raised when the key generation process
                fails.

        Example:
            >>> engine = CryptographyEngine()
            >>> key = engine.create_symmetric_key(
            ...     CryptographicAlgorithm.AES, 256)
        """
        if algorithm not in self._symmetric_key_algorithms.keys():
            raise exceptions.InvalidField(
                "The cryptographic algorithm {0} is not a supported symmetric "
                "key algorithm.".format(algorithm)
            )

        cryptography_algorithm = self._symmetric_key_algorithms.get(algorithm)

        if length not in cryptography_algorithm.key_sizes:
            raise exceptions.InvalidField(
                "The cryptographic length ({0}) is not valid for "
                "the cryptographic algorithm ({1}).".format(
                    length, algorithm.name
                )
            )

        self.logger.info(
            "Generating a {0} symmetric key with length: {1}".format(
                algorithm.name, length
            )
        )

        key_bytes = os.urandom(length // 8)
        try:
            cryptography_algorithm(key_bytes)
        except Exception as e:
            self.logger.exception(e)
            raise exceptions.CryptographicFailure(
                "Invalid bytes for the provided cryptographic algorithm.")

        return {'value': key_bytes, 'format': enums.KeyFormatType.RAW}

    def create_asymmetric_key_pair(self, algorithm, length):
        """
        Create an asymmetric key pair.

        Args:
            algorithm(CryptographicAlgorithm): An enumeration specifying the
                algorithm for which the created keys will be compliant.
            length(int): The length of the keys to be created. This value must
                be compliant with the constraints of the provided algorithm.

        Returns:
            dict: A dictionary containing the public key data, with at least
                the following key/value fields:
                * value - the bytes of the key
                * format - a KeyFormatType enumeration for the bytes format
            dict: A dictionary containing the private key data, identical in
                structure to the one above.

        Raises:
            InvalidField: Raised when the algorithm is unsupported or the
                length is incompatible with the algorithm.
            CryptographicFailure: Raised when the key generation process
                fails.

        Example:
            >>> engine = CryptographyEngine()
            >>> key = engine.create_asymmetric_key(
            ...     CryptographicAlgorithm.RSA, 2048)
        """
        if algorithm not in self._asymmetric_key_algorithms.keys():
            raise exceptions.InvalidField(
                "The cryptographic algorithm ({0}) is not a supported "
                "asymmetric key algorithm.".format(algorithm)
            )

        engine_method = self._asymmetric_key_algorithms.get(algorithm)
        return engine_method(length)

    def mac(self, algorithm, key, data):
        """
        Generate message authentication code.

        Args:
            algorithm(CryptographicAlgorithm): An enumeration specifying the
                algorithm for which the MAC operation will use.
            key(bytes): secret key used in the MAC operation
            data(bytes): The data to be MACed.

        Returns:
            bytes: The MACed data

        Raises:
            InvalidField: Raised when the algorithm is unsupported or the
                length is incompatible with the algorithm.
            CryptographicFailure: Raised when the key generation process
                fails.

        Example:
            >>> engine = CryptographyEngine()
            >>> mac_data = engine.mac(
            ...     CryptographicAlgorithm.HMAC-SHA256, b'\x01\x02\x03\x04',
            ...     b'\x05\x06\x07\x08')
        """

        mac_data = None

        if algorithm in self._hash_algorithms.keys():
            self.logger.info(
                "Generating a hash-based message authentication code using "
                "{0}".format(algorithm.name)
            )
            hash_algorithm = self._hash_algorithms.get(algorithm)
            try:
                h = hmac.HMAC(key, hash_algorithm(), backend=default_backend())
                h.update(data)
                mac_data = h.finalize()
            except Exception as e:
                self.logger.exception(e)
                raise exceptions.CryptographicFailure(
                    "An error occurred while computing an HMAC. "
                    "See the server log for more information."
                )
        elif algorithm in self._symmetric_key_algorithms.keys():
            self.logger.info(
                "Generating a cipher-based message authentication code using "
                "{0}".format(algorithm.name)
            )
            cipher_algorithm = self._symmetric_key_algorithms.get(algorithm)
            try:
                # ARC4 and IDEA algorithms will raise exception as CMAC
                # requires block ciphers
                c = cmac.CMAC(cipher_algorithm(key), backend=default_backend())
                c.update(data)
                mac_data = c.finalize()
            except Exception as e:
                raise exceptions.CryptographicFailure(
                    "An error occurred while computing a CMAC. "
                    "See the server log for more information."
                )
        else:
            raise exceptions.InvalidField(
                "The cryptographic algorithm ({0}) is not a supported "
                "for a MAC operation.".format(algorithm)
            )
        return mac_data

    def encrypt(self,
                encryption_algorithm,
                encryption_key,
                plain_text,
                cipher_mode=None,
                padding_method=None,
                iv_nonce=None):
        """
        Encrypt data using symmetric encryption.

        Args:
            encryption_algorithm (CryptographicAlgorithm): An enumeration
                specifying the symmetric encryption algorithm to use for
                encryption.
            encryption_key (bytes): The bytes of the symmetric key to use for
                encryption.
            plain_text (bytes): The bytes to be encrypted.
            cipher_mode (BlockCipherMode): An enumeration specifying the
                block cipher mode to use with the encryption algorithm.
                Required in the general case. Optional if the encryption
                algorithm is RC4 (aka ARC4). If optional, defaults to None.
            padding_method (PaddingMethod): An enumeration specifying the
                padding method to use on the data before encryption. Required
                if the cipher mode is for block ciphers (e.g., CBC, ECB).
                Optional otherwise, defaults to None.
            iv_nonce (bytes): The IV/nonce value to use to initialize the mode
                of the encryption algorithm. Optional, defaults to None. If
                required and not provided, it will be autogenerated and
                returned with the cipher text.

        Returns:
            dict: A dictionary containing the encrypted data, with at least
                the following key/value fields:
                * cipher_text - the bytes of the encrypted data
                * iv_nonce - the bytes of the IV/counter/nonce used if it
                    was needed by the encryption scheme and if it was
                    automatically generated for the encryption

        Raises:
            InvalidField: Raised when the algorithm is unsupported or the
                length is incompatible with the algorithm.
            CryptographicFailure: Raised when the key generation process
                fails.

        Example:
            >>> engine = CryptographyEngine()
            >>> result = engine.encrypt(
            ...     encryption_algorithm=CryptographicAlgorithm.AES,
            ...     encryption_key=(
            ...         b'\xF3\x96\xE7\x1C\xCF\xCD\xEC\x1F'
            ...         b'\xFC\xE2\x8E\xA6\xF8\x74\x28\xB0'
            ...     ),
            ...     plain_text=(
            ...         b'\x00\x01\x02\x03\x04\x05\x06\x07'
            ...         b'\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F'
            ...     ),
            ...     cipher_mode=BlockCipherMode.CBC,
            ...     padding_method=PaddingMethod.ANSI_X923,
            ... )
            >>> result.get('cipher_text')
            b'\x18[\xb9y\x1bL\xd1\x8f\x9a\xa0e\x02b\xa3=c'
            >>> result.iv_counter_nonce
            b'8qA\x05\xc4\x86\x03\xd9=\xef\xdf\xb8ke\x9a\xa2'
        """

        # Set up the algorithm
        if encryption_algorithm is None:
            raise exceptions.InvalidField("Encryption algorithm is required.")
        algorithm = self._symmetric_key_algorithms.get(
            encryption_algorithm,
            None
        )
        if algorithm is None:
            raise exceptions.InvalidField(
                "Encryption algorithm '{0}' is not a supported symmetric "
                "encryption algorithm.".format(encryption_algorithm)
            )
        try:
            algorithm = algorithm(encryption_key)
        except Exception as e:
            self.logger.exception(e)
            raise exceptions.CryptographicFailure(
                "Invalid key bytes for the specified encryption algorithm."
            )

        # Set up the cipher mode if needed
        return_iv_nonce = False
        if encryption_algorithm == enums.CryptographicAlgorithm.RC4:
            mode = None
        else:
            if cipher_mode is None:
                raise exceptions.InvalidField("Cipher mode is required.")
            mode = self._modes.get(cipher_mode, None)
            if mode is None:
                raise exceptions.InvalidField(
                    "Cipher mode '{0}' is not a supported mode.".format(
                        cipher_mode
                    )
                )
            if hasattr(mode, 'initialization_vector') or \
                    hasattr(mode, 'nonce'):
                if iv_nonce is None:
                    iv_nonce = os.urandom(algorithm.block_size // 8)
                    return_iv_nonce = True
                mode = mode(iv_nonce)
            else:
                mode = mode()

        # Pad the plain text if needed (separate methods for testing purposes)
        if cipher_mode in [
                enums.BlockCipherMode.CBC,
                enums.BlockCipherMode.ECB
        ]:
            plain_text = self._handle_symmetric_padding(
                self._symmetric_key_algorithms.get(encryption_algorithm),
                plain_text,
                padding_method
            )

        # Encrypt the plain text
        cipher = ciphers.Cipher(algorithm, mode, backend=default_backend())
        encryptor = cipher.encryptor()
        cipher_text = encryptor.update(plain_text) + encryptor.finalize()

        if return_iv_nonce:
            return {
                'cipher_text': cipher_text,
                'iv_nonce': iv_nonce
            }
        else:
            return {'cipher_text': cipher_text}

    def _handle_symmetric_padding(self,
                                  algorithm,
                                  plain_text,
                                  padding_method,
                                  undo_padding=False):
        # KMIP 1.3 test TC-STREAM-ENC-2-13.xml demonstrates a case
        # where an encrypt call for 3DES-ECB does not use padding if
        # the plaintext fits the blocksize of the algorithm. This does
        # not appear to be documented explicitly in the KMIP spec. It
        # also makes failures during unpadding after decryption
        # impossible to differentiate from cipher text/key mismatches.
        # For now, ALWAYS apply padding regardless of plain text length.
        if padding_method in self._symmetric_padding_methods.keys():
            padding_method = self._symmetric_padding_methods.get(
                padding_method
            )
            if undo_padding:
                padder = padding_method(algorithm.block_size).unpadder()
            else:
                padder = padding_method(algorithm.block_size).padder()
            plain_text = padder.update(plain_text)
            plain_text += padder.finalize()
        else:
            if padding_method is None:
                raise exceptions.InvalidField(
                    "Padding method is required."
                )
            else:
                raise exceptions.InvalidField(
                    "Padding method '{0}' is not supported.".format(
                        padding_method
                    )
                )
        return plain_text

    def decrypt(self,
                decryption_algorithm,
                decryption_key,
                cipher_text,
                cipher_mode=None,
                padding_method=None,
                iv_nonce=None):
        """
        Decrypt data using symmetric decryption.

        Args:
            decryption_algorithm (CryptographicAlgorithm): An enumeration
                specifying the symmetric decryption algorithm to use for
                decryption.
            decryption_key (bytes): The bytes of the symmetric key to use for
                decryption.
            cipher_text (bytes): The bytes to be decrypted.
            cipher_mode (BlockCipherMode): An enumeration specifying the
                block cipher mode to use with the decryption algorithm.
                Required in the general case. Optional if the decryption
                algorithm is RC4 (aka ARC4). If optional, defaults to None.
            padding_method (PaddingMethod): An enumeration specifying the
                padding method to use on the data after decryption. Required
                if the cipher mode is for block ciphers (e.g., CBC, ECB).
                Optional otherwise, defaults to None.
            iv_nonce (bytes): The IV/nonce value to use to initialize the mode
                of the decryption algorithm. Optional, defaults to None.

        Returns:
            bytes: the bytes of the decrypted data

        Raises:
            InvalidField: Raised when the algorithm is unsupported or the
                length is incompatible with the algorithm.
            CryptographicFailure: Raised when the key generation process
                fails.

        Example:
            >>> engine = CryptographyEngine()
            >>> result = engine.decrypt(
            ...     decryption_algorithm=CryptographicAlgorithm.AES,
            ...     decryption_key=(
            ...         b'\xF3\x96\xE7\x1C\xCF\xCD\xEC\x1F'
            ...         b'\xFC\xE2\x8E\xA6\xF8\x74\x28\xB0'
            ...     ),
            ...     cipher_text=(
            ...         b'\x18\x5B\xB9\x79\x1B\x4C\xD1\x8F'
            ...         b'\x9A\xA0\x65\x02\x62\xA3\x3D\x63'
            ...     ),
            ...     cipher_mode=BlockCipherMode.CBC,
            ...     padding_method=PaddingMethod.ANSI_X923,
            ...     iv_nonce=(
            ...         b'\x38\x71\x41\x05\xC4\x86\x03\xD9'
            ...         b'\x3D\xEF\xDF\xB8\x6B\x65\x9A\xA2'
            ...     )
            ... )
            >>> result
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
        """

        # Set up the algorithm
        if decryption_algorithm is None:
            raise exceptions.InvalidField("Decryption algorithm is required.")
        algorithm = self._symmetric_key_algorithms.get(
            decryption_algorithm,
            None
        )
        if algorithm is None:
            raise exceptions.InvalidField(
                "Decryption algorithm '{0}' is not a supported symmetric "
                "decryption algorithm.".format(decryption_algorithm)
            )
        try:
            algorithm = algorithm(decryption_key)
        except Exception as e:
            self.logger.exception(e)
            raise exceptions.CryptographicFailure(
                "Invalid key bytes for the specified decryption algorithm."
            )

        # Set up the cipher mode if needed
        if decryption_algorithm == enums.CryptographicAlgorithm.RC4:
            mode = None
        else:
            if cipher_mode is None:
                raise exceptions.InvalidField("Cipher mode is required.")
            mode = self._modes.get(cipher_mode, None)
            if mode is None:
                raise exceptions.InvalidField(
                    "Cipher mode '{0}' is not a supported mode.".format(
                        cipher_mode
                    )
                )
            if hasattr(mode, 'initialization_vector') or \
                    hasattr(mode, 'nonce'):
                if iv_nonce is None:
                    raise exceptions.InvalidField(
                        "IV/nonce is required."
                    )
                mode = mode(iv_nonce)
            else:
                mode = mode()

        # Decrypt the plain text
        cipher = ciphers.Cipher(algorithm, mode, backend=default_backend())
        decryptor = cipher.decryptor()
        plain_text = decryptor.update(cipher_text) + decryptor.finalize()

        # Unpad the plain text if needed (separate methods for testing
        # purposes)
        if cipher_mode in [
                enums.BlockCipherMode.CBC,
                enums.BlockCipherMode.ECB
        ]:
            plain_text = self._handle_symmetric_padding(
                self._symmetric_key_algorithms.get(decryption_algorithm),
                plain_text,
                padding_method
            )

        return plain_text

    def _create_rsa_key_pair(self, length, public_exponent=65537):
        """
        Create an RSA key pair.

        Args:
            length(int): The length of the keys to be created. This value must
                be compliant with the constraints of the provided algorithm.
            public_exponent(int): The value of the public exponent needed to
                generate the keys. Usually a small Fermat prime number.
                Optional, defaults to 65537.

        Returns:
            dict: A dictionary containing the public key data, with the
                following key/value fields:
                * value - the bytes of the key
                * format - a KeyFormatType enumeration for the bytes format
                * public_exponent - the public exponent integer
            dict: A dictionary containing the private key data, identical in
                structure to the one above.

        Raises:
            CryptographicFailure: Raised when the key generation process
                fails.
        """
        self.logger.info(
            "Generating an RSA key pair with length: {0}, and "
            "public_exponent: {1}".format(
                length, public_exponent
            )
        )
        try:
            private_key = rsa.generate_private_key(
                public_exponent=public_exponent,
                key_size=length,
                backend=default_backend())
            public_key = private_key.public_key()

            private_bytes = private_key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption())
            public_bytes = public_key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.PKCS1)
        except Exception as e:
            self.logger.exception(e)
            raise exceptions.CryptographicFailure(
                "An error occurred while generating the RSA key pair. "
                "See the server log for more information."
            )

        public_key = {
            'value': public_bytes,
            'format': enums.KeyFormatType.PKCS_1,
            'public_exponent': public_exponent
        }
        private_key = {
            'value': private_bytes,
            'format': enums.KeyFormatType.PKCS_8,
            'public_exponent': public_exponent
        }

        return public_key, private_key

    def derive_key(self,
                   derivation_method,
                   derivation_length,
                   derivation_data=None,
                   key_material=None,
                   hash_algorithm=None,
                   salt=None,
                   iteration_count=None,
                   encryption_algorithm=None,
                   cipher_mode=None,
                   padding_method=None,
                   iv_nonce=None):
        """
        Derive key data using a variety of key derivation functions.

        Args:
            derivation_method (DerivationMethod): An enumeration specifying
                the key derivation method to use. Required.
            derivation_length (int): An integer specifying the size of the
                derived key data in bytes. Required.
            derivation_data (bytes): The non-cryptographic bytes to be used
                in the key derivation process (e.g., the data to be encrypted,
                hashed, HMACed). Required in the general case. Optional if the
                derivation method is Hash and the key material is provided.
                Optional, defaults to None.
            key_material (bytes): The bytes of the key material to use for
                key derivation. Required in the general case. Optional if
                the derivation_method is HASH and derivation_data is provided.
                Optional, defaults to None.
            hash_algorithm (HashingAlgorithm): An enumeration specifying the
                hashing algorithm to use with the key derivation method.
                Required in the general case, optional if the derivation
                method specifies encryption. Optional, defaults to None.
            salt (bytes): Bytes representing a randomly generated salt.
                Required if the derivation method is PBKDF2. Optional,
                defaults to None.
            iteration_count (int): An integer representing the number of
                iterations to use when deriving key material. Required if
                the derivation method is PBKDF2. Optional, defaults to None.
            encryption_algorithm (CryptographicAlgorithm): An enumeration
                specifying the symmetric encryption algorithm to use for
                encryption-based key derivation. Required if the derivation
                method specifies encryption. Optional, defaults to None.
            cipher_mode (BlockCipherMode): An enumeration specifying the
                block cipher mode to use with the encryption algorithm.
                Required in in the general case if the derivation method
                specifies encryption and the encryption algorithm is
                specified. Optional if the encryption algorithm is RC4 (aka
                ARC4). Optional, defaults to None.
            padding_method (PaddingMethod): An enumeration specifying the
                padding method to use on the data before encryption. Required
                in in the general case if the derivation method specifies
                encryption and the encryption algorithm is specified. Required
                if the cipher mode is for block ciphers (e.g., CBC, ECB).
                Optional otherwise, defaults to None.
            iv_nonce (bytes): The IV/nonce value to use to initialize the mode
                of the encryption algorithm. Required in the general case if
                the derivation method specifies encryption and the encryption
                algorithm is specified. Optional, defaults to None. If
                required and not provided, it will be autogenerated.

        Returns:
            bytes: the bytes of the derived data

        Raises:
            InvalidField: Raised when cryptographic data and/or settings are
                unsupported or incompatible with the derivation method.

        Example:
            >>> engine = CryptographyEngine()
            >>> result = engine.derive_key(
            ...     derivation_method=enums.DerivationMethod.HASH,
            ...     derivation_length=16,
            ...     derivation_data=b'abc',
            ...     hash_algorithm=enums.HashingAlgorithm.MD5
            ... )
            >>> result
            b'\x90\x01P\x98<\xd2O\xb0\xd6\x96?}(\xe1\x7fr'
        """
        if derivation_method == enums.DerivationMethod.ENCRYPT:
            result = self.encrypt(
                encryption_algorithm=encryption_algorithm,
                encryption_key=key_material,
                plain_text=derivation_data,
                cipher_mode=cipher_mode,
                padding_method=padding_method,
                iv_nonce=iv_nonce
            )
            return result.get('cipher_text')
        else:
            # Handle key derivation functions that use hash algorithms

            # Set up the hashing algorithm
            if hash_algorithm is None:
                raise exceptions.InvalidField("Hash algorithm is required.")
            hashing_algorithm = self._encryption_hash_algorithms.get(
                hash_algorithm,
                None
            )
            if hashing_algorithm is None:
                raise exceptions.InvalidField(
                    "Hash algorithm '{0}' is not a supported hashing "
                    "algorithm.".format(hash_algorithm)
                )

            if derivation_method == enums.DerivationMethod.HMAC:
                df = hkdf.HKDF(
                    algorithm=hashing_algorithm(),
                    length=derivation_length,
                    salt=salt,
                    info=derivation_data,
                    backend=default_backend()
                )
                derived_data = df.derive(key_material)
                return derived_data
            elif derivation_method == enums.DerivationMethod.HASH:
                if None not in [derivation_data, key_material]:
                    raise exceptions.InvalidField(
                        "For hash-based key derivation, specify only "
                        "derivation data or key material, not both."
                    )
                elif derivation_data is not None:
                    hashing_data = derivation_data
                elif key_material is not None:
                    hashing_data = key_material
                else:
                    raise exceptions.InvalidField(
                        "For hash-based key derivation, derivation data or "
                        "key material must be specified."
                    )

                df = hashes.Hash(
                    algorithm=hashing_algorithm(),
                    backend=default_backend()
                )
                df.update(hashing_data)
                derived_data = df.finalize()
                return derived_data
            elif derivation_method == enums.DerivationMethod.PBKDF2:
                if salt is None:
                    raise exceptions.InvalidField(
                        "For PBKDF2 key derivation, salt must be specified."
                    )
                if iteration_count is None:
                    raise exceptions.InvalidField(
                        "For PBKDF2 key derivation, iteration count must be "
                        "specified."
                    )

                df = pbkdf2.PBKDF2HMAC(
                    algorithm=hashing_algorithm(),
                    length=derivation_length,
                    salt=salt,
                    iterations=iteration_count,
                    backend=default_backend()
                )
                derived_data = df.derive(key_material)
                return derived_data
            elif derivation_method == enums.DerivationMethod.NIST800_108_C:
                df = kbkdf.KBKDFHMAC(
                    algorithm=hashing_algorithm(),
                    mode=kbkdf.Mode.CounterMode,
                    length=derivation_length,
                    rlen=4,
                    llen=None,
                    location=kbkdf.CounterLocation.BeforeFixed,
                    label=None,
                    context=None,
                    fixed=derivation_data,
                    backend=default_backend()
                )
                derived_data = df.derive(key_material)
                return derived_data
            else:
                raise exceptions.InvalidField(
                    "Derivation method '{0}' is not a supported key "
                    "derivation method.".format(derivation_method)
                )

    def wrap_key(self,
                 key_material,
                 wrapping_method,
                 key_wrap_algorithm,
                 encryption_key):
        """
        Args:
            key_material (bytes): The bytes of the key to wrap. Required.
            wrapping_method (WrappingMethod): A WrappingMethod enumeration
                specifying what wrapping technique to use to wrap the key
                material. Required.
            key_wrap_algorithm (BlockCipherMode): A BlockCipherMode
                enumeration specifying the key wrapping algorithm to use to
                wrap the key material. Required.
            encryption_key (bytes): The bytes of the encryption key to use
                to encrypt the key material. Required.

        Returns:
            bytes: the bytes of the wrapped key

        Raises:
            CryptographicFailure: Raised when an error occurs during key
                wrapping.
            InvalidField: Raised when an unsupported wrapping or encryption
                algorithm is specified.

        Example:
            >>> engine = CryptographyEngine()
            >>> result = engine.wrap_key(
            ...     key_material=(
            ...         b'\x00\x11\x22\x33\x44\x55\x66\x77'
            ...         b'\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF'
            ...     )
            ...     wrapping_method=enums.WrappingMethod.ENCRYPT,
            ...     key_wrap_algorithm=enums.BlockCipherMode.NIST_KEY_WRAP,
            ...     encryption_key=(
            ...         b'\x00\x01\x02\x03\x04\x05\x06\x07'
            ...         b'\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F'
            ...     )
            ... )
            >>> result
            b'\x1f\xa6\x8b\n\x81\x12\xb4G\xae\xf3K\xd8\xfbZ{\x82\x9d>\x86#q
            \xd2\xcf\xe5'
        """
        if wrapping_method == enums.WrappingMethod.ENCRYPT:
            if key_wrap_algorithm == enums.BlockCipherMode.NIST_KEY_WRAP:
                try:
                    wrapped_key = keywrap.aes_key_wrap(
                        encryption_key,
                        key_material,
                        default_backend()
                    )
                    return wrapped_key
                except Exception as e:
                    raise exceptions.CryptographicFailure(str(e))
            else:
                raise exceptions.InvalidField(
                    "Encryption algorithm '{0}' is not a supported key "
                    "wrapping algorithm.".format(key_wrap_algorithm)
                )
        else:
            raise exceptions.InvalidField(
                "Wrapping method '{0}' is not a supported key wrapping "
                "method.".format(wrapping_method)
            )
