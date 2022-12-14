import json
import os
from pathlib import Path
import random
import re
import tempfile
import requests
import shutil
import logging
from Crypto.Cipher import AES
from Crypto.Util import Counter
from collections import defaultdict
from mega.crypto import base64_to_a32, base64_url_decode, decrypt_attr, decrypt_key, a32_to_str, get_chunks, str_to_a32
from mega.errors import ValidationError, RequestError

sid = ''
seqno = random.randint(0, 0xFFFFFFFF)
logger = logging.getLogger(__name__)
timeout = 160

def download_file(file_handle,
                       file_key,
                       file_data, 
                       dest_path=None,
                       dest_filename=None):

        k = (file_key[0] ^ file_key[4], file_key[1] ^ file_key[5],
                file_key[2] ^ file_key[6], file_key[3] ^ file_key[7])
        iv = file_key[4:6] + (0, 0)
        meta_mac = file_key[6:8]

        # Seems to happens sometime... When this occurs, files are
        # inaccessible also in the official also in the official web app.
        # Strangely, files can come back later.
        if 'g' not in file_data:
            raise RequestError('File not accessible anymore')
        file_url = file_data['g']
        file_size = file_data['s']
        attribs = base64_url_decode(file_data['at'])
        attribs = decrypt_attr(attribs, k)

        file_name = attribs['n']

        input_file = requests.get(file_url, stream=True).raw

        if dest_path is None:
            dest_path = ''
        else:
            dest_path += '/'

        with tempfile.NamedTemporaryFile(mode='w+b',
                                         prefix='megapy_',
                                         delete=False) as temp_output_file:
            k_str = a32_to_str(k)
            counter = Counter.new(128,
                                  initial_value=((iv[0] << 32) + iv[1]) << 64)
            aes = AES.new(k_str, AES.MODE_CTR, counter=counter)

            mac_str = '\0' * 16
            mac_encryptor = AES.new(k_str, AES.MODE_CBC,
                                    mac_str.encode("utf8"))
            iv_str = a32_to_str([iv[0], iv[1], iv[0], iv[1]])

            for chunk_start, chunk_size in get_chunks(file_size):
                chunk = input_file.read(chunk_size)
                chunk = aes.decrypt(chunk)
                temp_output_file.write(chunk)

                encryptor = AES.new(k_str, AES.MODE_CBC, iv_str)
                for i in range(0, len(chunk) - 16, 16):
                    block = chunk[i:i + 16]
                    encryptor.encrypt(block)

                # fix for files under 16 bytes failing
                if file_size > 16:
                    i += 16
                else:
                    i = 0

                block = chunk[i:i + 16]
                if len(block) % 16:
                    block += b'\0' * (16 - (len(block) % 16))
                mac_str = mac_encryptor.encrypt(encryptor.encrypt(block))

                file_info = os.stat(temp_output_file.name)
                logger.info('%s of %s downloaded', file_info.st_size,
                            file_size)
            file_mac = str_to_a32(mac_str)
            # check mac integrity
            if (file_mac[0] ^ file_mac[1],
                    file_mac[2] ^ file_mac[3]) != meta_mac:
                raise ValueError('Mismatched mac')
            output_path = Path(dest_path + file_name)
        shutil.move(temp_output_file.name, output_path)
        return output_path
            
def get_file_data(file_id: str, root_folder: str):
    data = [{ 'a': 'g', 'g': 1, 'n': file_id }]
    response = requests.post(
        "https://g.api.mega.co.nz/cs",
        params={'id': 0,  # self.sequence_num
                'n': root_folder},
        data=json.dumps(data)
    )
    json_resp = response.json()
    return json_resp[0]

#def get_nodes_in_shared_folder(root_folder: str) -> dict:
def get_nodes_in_shared_folder(root_folder: str):
    data = [{"a": "f", "c": 1, "ca": 1, "r": 1}]
    response = requests.post(
        "https://g.api.mega.co.nz/cs",
        params={'id': 0,  # self.sequence_num
                'n': root_folder},
        data=json.dumps(data)
    )
    json_resp = response.json()
    return json_resp[0]["f"]

#def parse_folder_url(url: str) -> Tuple[str, str]:
def parse_folder_url(url: str):
    "Returns (public_handle, key) if valid. If not returns None."
    REGEXP1 = re.compile(r"mega.[^/]+/folder/([0-z-_]+)#([0-z-_]+)(?:/folder/([0-z-_]+))*")
    REGEXP2 = re.compile(r"mega.[^/]+/#F!([0-z-_]+)[!#]([0-z-_]+)(?:/folder/([0-z-_]+))*")
    m = re.search(REGEXP1, url)
    if not m:
        m = re.search(REGEXP2, url)
    if not m:
        print("Not a valid URL")
        return None
    root_folder = m.group(1)
    key = m.group(2)
    # You may want to use m.groups()[-1]
    # to get the id of the subfolder
    return (root_folder, key)

#def decrypt_node_key(key_str: str, shared_key: str) -> Tuple[int, ...]:
def decrypt_node_key(key_str: str, shared_key: str):
    encrypted_key = base64_to_a32(key_str.split(":")[1])
    return decrypt_key(encrypted_key, shared_key)


#(root_folder, shared_enc_key) = parse_folder_url("https://mega.nz/folder/DfBWGTjA#BFcNX-XcMEnY-cdFDWTx1Q")
#shared_key = base64_to_a32(shared_enc_key)
#nodes = get_nodes_in_shared_folder(root_folder)
#for node in nodes:
#    key = decrypt_node_key(node["k"], shared_key)
#    if node["t"] == 0: # Is a file
#        k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
#    elif node["t"] == 1: # Is a folder
#        k = key
#    attrs = decrypt_attr(base64_url_decode(node["a"]), k)
#    file_name = attrs["n"]
#    file_id = node["h"]
#    print("file_name: {}\tfile_id: {}".format(file_name, file_id))
#    if node["t"] == 0:
#        file_data = get_encryption_key(file_id, root_folder)
#        download_file(file_id, key, file_data)
def get_files(url: str, files: list, directories: dict):
    (folder, shared_enc_key) = parse_folder_url(url)
    shared_key = base64_to_a32(shared_enc_key)
    nodes = get_nodes_in_shared_folder(folder)
    for node in nodes:
        key = decrypt_node_key(node["k"], shared_key)
        if node["t"] == 0: # Is a file
            k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
        elif node["t"] == 1: # Is a folder
            k = key
        if node["t"] == 0:
            attrs = decrypt_attr(base64_url_decode(node["a"]), k)
            file_name = attrs["n"]
            file_id = node["h"]
            parent_id = node["p"]
            print("file_name: {}\tfile_id: {}\tparent_id: {}".format(file_name, file_id, parent_id))
            #print("file_name: {}\tfile_id: {}".format(file_name, file_id))
            file_data = get_file_data(file_id, folder)
            files["files"].append({"size": file_data["s"], "file_name": file_name, "file_id": file_id, "parent_id": parent_id, "file_data": file_data})
            files["total_size"] += file_data["s"]
            files["total_files"] += 1
        else:
            attrs = decrypt_attr(base64_url_decode(node["a"]), k)
            file_name = attrs["n"]
            file_id = node["h"]
            parent_id = node["p"]
            directories[file_id] = {"file_name": file_name, "parent_id": parent_id}
            print("file_name: {}\tfile_id: {}\tparent_id: {}".format(file_name, file_id, parent_id))
            #print(attrs)

def get_full_path(file_id: str, directories: dict):
    full_path = ""
    if file_id in directories:
        full_path = directories[file_id]["file_name"] + "/"
        parent_id = directories[file_id]["parent_id"]

        while parent_id in directories:
            full_path = directories[parent_id]["file_name"] + "/" + full_path
            parent_id = directories[parent_id]["parent_id"]

    return full_path

file_list = {"total_size": 0, "total_files": 0, "files": []}
directories = {}
get_files("https://mega.nz/folder/O8Yi3bKK#Rqh30Iu-t3zIFxMrnTp3Nw", file_list, directories)
for i in file_list["files"]:
    print(get_full_path(i["parent_id"], directories) + i["file_name"])

#(root_folder, shared_enc_key) = parse_folder_url("https://mega.nz/folder/O8Yi3bKK#Rqh30Iu-t3zIFxMrnTp3Nw")
#shared_key = base64_to_a32(shared_enc_key)
#(root_folder, shared_enc_key) = parse_folder_url("https://mega.nz/folder/O8Yi3bKK#Rqh30Iu-t3zIFxMrnTp3Nw/folder/DgoFgQyK")
#shared_key = base64_to_a32(shared_enc_key)
#nodes = get_nodes_in_shared_folder(root_folder)
#for node in nodes:
#    key = decrypt_node_key(node["k"], shared_key)
#    if node["t"] == 0: # Is a file
#        k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
#    elif node["t"] == 1: # Is a folder
#        k = key


#h: ID of node <ID-NODE>
#p: ID of parent node (directory)
#u: Owner of node
#t: type of node (0: file, 1: directory, 2: Root, 3: Inbox, 4: Trash bin)
#a: Attributes (name)
#k: Key <KEY-NODE>
#s: Size of node
#ts: Last modified time