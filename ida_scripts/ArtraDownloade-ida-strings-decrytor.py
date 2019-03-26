from idautils import *
from idc import *

############################################################################
# ArtraDownloader v1 - strings decryptor
#
# Ref sample:
#	file name: winsvc
#   md5: 7cc0b212d1b8ceb808c250495d83bae4  
#   sha1: d2c161ce52240b61d632607a2262890327d82502
#   sha256: ef0cb0a1a29bcdf2b36622f72734aec8d38326fc8f7270f78bd956e706a5fd57
#
# Ref links: 
#	2018.12.19 https://twitter.com/malwrhunterteam/status/1075454863008382976
#	2018.12.21 https://gist.github.com/raw-data/14915eca4e5e2963a9056f935442358d
#	2019.02.25 https://unit42.paloaltonetworks.com/multiple-artradownloader-variants-used-by-bitter-to-target-pakistan/
############################################################################

__author__ = 'raw-data'

def decrypt_string(enc_str):
	mapping = (enc_str, ''.join([chr(ord(char) - 1) for char in enc_str]))
	return(mapping[1])

def get_string(addr):
	return GetString(addr)

def get_function_args(addr):
  while True:
    addr = idc.PrevHead(addr)
    if GetMnem(addr) == "mov" and "eax" in GetOpnd(addr, 0):
      return GetOperandValue(addr, 1)
      break

def extract_encrypted_str(xrefs):
	for addr in xrefs:
	  ref = get_function_args((addr.frm))
	  enc_str = get_string(ref)
	  dec_str = decrypt_string(enc_str)

	  # add comments
	  MakeComm(addr.frm, dec_str)
	  MakeComm(ref, dec_str)

	  # print results to console
	  print("Address: %-40s Enc string: %-40s Dec string: %-40s" % (addr.frm, dec_str, dec_str))

def run():
	xrefs = XrefsTo(0x004026b0, flags=0)
	extract_encrypted_str(xrefs)

run()