import sys
import os
import stat
import subprocess
from shutil import copyfile

def word2list(a):
	return a & 0xff, a >> 8

encfile_dir = sys.argv[1]
outfile_dir = sys.argv[2]

devnull = open(os.devnull, 'wb')
encfile = open(encfile_dir, 'rb')
enc_header = encfile.read(0x10)
encfile.close()

def inverse_xor(enc_header):
	dec_header = [0 for i in range(16)]
	dec_header[0] = enc_header[0]
	dec_header[2] = enc_header[2]
	dec_header[4] = enc_header[4]
	dec_header[10] = enc_header[3]
	dec_header[12] = enc_header[5]
	dec_header[6]  = enc_header[6]
	dec_header[14] = enc_header[7]
	dec_header[15] = enc_header[6] ^ enc_header[15]
	dec_header[8] = enc_header[8] ^ dec_header[15]
	dec_header[1] = enc_header[1] ^ dec_header[8]
	return dec_header

def re_xor(dec_header):
	for i in range(16):
		dec_header[i] = (dec_header[i] ^ dec_header[(i + 7) % 16])
	return dec_header

def to_time(dec_header):
	time = []
	for i in range(0, len(dec_header),2):
		time.append((dec_header[i+1] * 0x100) + dec_header[i])
	return time

def make_masterkey_table(dec_header):
	masterkey_table = []
	while time[7] != 0:
		time[7] -= 1
		dec_header[14] = word2list(time[7])[0]
		dec_header[15] = word2list(time[7])[1]
		new_dec_header = []
		new_dec_header += dec_header
		masterkey_table += ["".join(["%02X" % x for x in re_xor(new_dec_header)])]
	return masterkey_table

dec_header = inverse_xor(enc_header)
time = to_time(dec_header)
masterkey_table = make_masterkey_table(dec_header)

print('[*] Volume Create Time : %s %s %s %s %s %s %s %s' % (time[0],time[1],time[2],time[3],time[4],time[5],time[6],time[7]))

subprocess.call('dmsetup remove VeraCrypt', shell=True, stdout=devnull, stderr=subprocess.STDOUT)

mode=os.lstat(encfile_dir).st_mode
isBLKDEV = stat.S_ISBLK(mode)

if isBLKDEV:
	loopdev = encfile_dir
else:
	losetupcmd = 'losetup ' + ' -f --show ' + encfile_dir
	losetupoutput = subprocess.check_output(losetupcmd, shell=True, universal_newlines=True)
	loopdev = losetupoutput[:-1]

evsize = str(int(subprocess.check_output(['blockdev', '--getsz', loopdev])) - 512)

print('[*] Start Brute-Force Attack')

for i in range(0, len(masterkey_table)):
	for j in range((i-3 if i > 3 else 0), i):
		for k in range((j-3 if j > 3 else 0), j):
			for o in range((k-3 if k > 3 else 0), k):
				masterkey = masterkey_table[i] + masterkey_table[j] + masterkey_table[k] + masterkey_table[o]
				try:
					cmd =  '"0 ' + evsize + ' crypt aes-xts-plain64 ' + masterkey + ' 256 ' + loopdev + ' 256"'
					subprocess.call('dmsetup create VeraCrypt --table ' + cmd, shell=True, stdout=devnull, stderr=subprocess.STDOUT)

					decfile = open('/dev/mapper/VeraCrypt', 'rb')
					decfile.seek(3)
					OEM = decfile.read(5)
					decfile.close()
						
					if OEM == str.encode('MSDOS'):
						print('[*] Found Key! : '+ masterkey)
						copyfile('/dev/mapper/VeraCrypt', outfile_dir)
						print('[*] Done!~')
						subprocess.call('dmsetup remove VeraCrypt', shell=True, stdout=devnull, stderr=subprocess.STDOUT)
						exit(0)
					else:
						subprocess.call('dmsetup remove VeraCrypt', shell=True, stdout=devnull, stderr=subprocess.STDOUT)
				except:
					subprocess.call('dmsetup remove VeraCrypt', shell=True, stdout=devnull, stderr=subprocess.STDOUT)