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

#@author raw-data
#@category malware strings decryptor
#@keybinding 
#@menupath 
#@toolbar 

import ghidra.app.script.GhidraScript
import exceptions

enc_buffer = []

listing = currentProgram.getListing()

def decrypt_string(enc_str):
	mapping = (enc_str, ''.join([chr(ord(char) - 1) for char in enc_str]))
	return(mapping[1])

def get_function_args(addr):
	while True:
		# get instruction at given address
		ins = getInstructionBefore(toAddr(addr))
		# get instruction offset address
		ins_addr = ins.getAddress()
		# check pattern
		get_ins = getInstructionAt(toAddr(addr))
		op = get_ins.toString().split()[0]
		if "MOV" == op and get_ins.getDefaultOperandRepresentation(0) == "EAX" and "0x" in get_ins.getDefaultOperandRepresentation(1):
			enc_string = getDataAt(toAddr(get_ins.getDefaultOperandRepresentation(1)))
			if enc_string:
				# map encrypted string and its offset address
				mapping = (toAddr(get_ins.getDefaultOperandRepresentation(1)), enc_string)
				enc_buffer.append(mapping)
			break
		else:
			get_function_args(ins_addr.toString())
		break

def extract_encrypted_str(xrefs):
	for xref in xrefs:
		ref_addr = (xref.getFromAddress())
		get_function_args(ref_addr.toString())

	decrypt_enc_str_and_comment()

def decrypt_enc_str_and_comment():
	for enc_str_addr, enc_str in enc_buffer:
		enc_str = enc_str.toString().split()[1].strip("\"")
		dec_str = decrypt_string(enc_str)
		
		# add comments
		codeUnit = listing.getCodeUnitAt(toAddr(enc_str_addr.toString()))
		ds_string = getDataAt(toAddr(enc_str_addr.toString()))
		ds_string.setComment(codeUnit.EOL_COMMENT, dec_str)
		
		# print results to console
		print("Address: %-40s Enc string: %-40s Dec string: %-40s" % (toAddr(enc_str_addr.toString()), enc_str, dec_str))

def run():
	xrefs = getReferencesTo(toAddr(0x004026b0))
	extract_encrypted_str(xrefs)

run()
