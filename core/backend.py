import os
import struct
import lzma
import tarfile
import io
import concurrent.futures
import brotli
import zstandard as zstd
import pyppmd
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC_HEADER = b'MYCF'
VERSION = 7  # Advanced: Solid + Threading

class SecureCompressor:
    def __init__(self):
        pass

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000,
        )
        return kdf.derive(password.encode('utf-8'))

    # --- WORKER FUNCTIONS FOR THREADING ---
    @staticmethod
    def try_lzma(data):
        try:
            filters = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME, "dict_size": 64*1024*1024}]
            res = lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)
            return (len(res), res, 1) # ID 1
        except: return None

    @staticmethod
    def try_brotli(data):
        try:
            res = brotli.compress(data, quality=11, lgwin=24)
            return (len(res), res, 2) # ID 2
        except: return None

    @staticmethod
    def try_zstd(data):
        try:
            cctx = zstd.ZstdCompressor(level=22)
            res = cctx.compress(data)
            return (len(res), res, 3) # ID 3
        except: return None

    @staticmethod
    def try_ppmd(data):
        try:
            res = pyppmd.compress(data, 6)
            return (len(res), res, 4) # ID 4
        except: return None

    # --- MAIN PROCESS (Renamed back to process_file to fix error) ---
    def process_file(self, input_path, output_path, password, mode='compress', callback=None):
        if mode == 'compress':
            return self._advanced_compress(input_path, output_path, password, callback)
        elif mode == 'decompress':
            return self._advanced_decompress(input_path, output_path, password, callback)

    def _advanced_compress(self, input_path, output_path, password, callback):
        # 1. HANDLE FOLDERS (SOLID MODE)
        if os.path.isdir(input_path):
            if callback: callback(0.1, "Solid Mode: Archiving Folder...")
            
            # Create a Tarball in RAM
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                tar.add(input_path, arcname=os.path.basename(input_path))
            
            raw_data = tar_buffer.getvalue()
            is_folder = True
        else:
            if callback: callback(0.1, "Reading File...")
            with open(input_path, 'rb') as f:
                raw_data = f.read()
            is_folder = False

        # 2. PARALLEL COMPRESSION RACE
        if callback: callback(0.3, "Racing 4 Algorithms (Parallel)...")
        
        candidates = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_lzma = executor.submit(self.try_lzma, raw_data)
            future_brotli = executor.submit(self.try_brotli, raw_data)
            future_zstd = executor.submit(self.try_zstd, raw_data)
            future_ppmd = executor.submit(self.try_ppmd, raw_data)

            results = [
                future_lzma.result(),
                future_brotli.result(),
                future_zstd.result(),
                future_ppmd.result()
            ]
            
            for res in results:
                if res: candidates.append(res)

        # Fallback
        candidates.append((len(raw_data), raw_data, 0))

        # 3. PICK WINNER
        if callback: callback(0.8, "Encrypting Winner...")
        best_size, best_data, method_id = sorted(candidates, key=lambda x: x[0])[0]

        # 4. ENCRYPT
        salt = os.urandom(16)
        key = self._derive_key(password, salt)
        aes = AESGCM(key)
        nonce = os.urandom(12)
        encrypted_data = aes.encrypt(nonce, best_data, None)

        # 5. SAVE HEADER
        with open(output_path, 'wb') as f:
            f.write(MAGIC_HEADER)
            f.write(struct.pack('B', VERSION))
            f.write(struct.pack('B', 1 if is_folder else 0)) 
            f.write(struct.pack('B', method_id)) 
            f.write(salt)
            f.write(nonce)
            f.write(encrypted_data)

        if callback: callback(1.0, "Done!")
        return True

    def _advanced_decompress(self, input_path, output_path, password, callback):
        if callback: callback(0.1, "Reading & Decrypting...")
        
        with open(input_path, 'rb') as f:
            if f.read(4) != MAGIC_HEADER: raise ValueError("Invalid file.")
            version = struct.unpack('B', f.read(1))[0]
            is_folder = struct.unpack('B', f.read(1))[0]
            method_id = struct.unpack('B', f.read(1))[0]
            salt = f.read(16)
            nonce = f.read(12)
            encrypted_data = f.read()

        try:
            key = self._derive_key(password, salt)
            aes = AESGCM(key)
            decrypted_data = aes.decrypt(nonce, encrypted_data, None)
        except:
            raise ValueError("Wrong password or corrupted.")

        if callback: callback(0.5, "Decompressing...")
        
        # Restore Data
        if method_id == 1:
            filters = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME, "dict_size": 64*1024*1024}]
            original = lzma.decompress(decrypted_data, format=lzma.FORMAT_RAW, filters=filters)
        elif method_id == 2: original = brotli.decompress(decrypted_data)
        elif method_id == 3: original = zstd.ZstdDecompressor().decompress(decrypted_data)
        elif method_id == 4: original = pyppmd.decompress(decrypted_data)
        else: original = decrypted_data

        if callback: callback(0.9, "Restoring...")

        # 6. HANDLE FOLDER EXTRACTION
        if is_folder == 1:
            tar_stream = io.BytesIO(original)
            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                # Remove extension to get folder name
                extract_path = output_path.replace(".extracted", "")
                if not os.path.exists(extract_path): os.makedirs(extract_path)
                tar.extractall(path=extract_path)
        else:
            with open(output_path, 'wb') as f:
                f.write(original)
        
        if callback: callback(1.0, "Done!")
        return True
